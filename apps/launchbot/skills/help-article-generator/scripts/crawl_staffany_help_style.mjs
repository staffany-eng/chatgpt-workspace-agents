import fs from 'node:fs/promises'

const SITEMAP_URL = 'https://help.staffany.com/sitemap.xml'
const OUT_PATH =
  '/private/tmp/staffany-help-center-style-analysis.json'
const DELAY_MS = 1050

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const decodeXml = (value) =>
  value
    .replaceAll('&amp;', '&')
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
    .replaceAll('&quot;', '"')
    .replaceAll('&apos;', "'")

const extractNextData = (html) => {
  const match = html.match(
    /<script id="__NEXT_DATA__" type="application\/json"[^>]*>([\s\S]*?)<\/script>/,
  )
  if (!match) {
    return null
  }
  return JSON.parse(match[1])
}

const stripHtml = (value = '') =>
  value
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&gt;/g, '>')
    .replace(/&lt;/g, '<')
    .replace(/&amp;/g, '&')
    .replace(/&nbsp;/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+\n/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .trim()

const blockToText = (block) => {
  if (!block) {
    return ''
  }

  if (block.type === 'image') {
    return '[image]'
  }

  if (block.type === 'table') {
    return '[table]'
  }

  if (block.text) {
    return stripHtml(block.text)
  }

  if (Array.isArray(block.items)) {
    return block.items
      .flatMap((item) => item.content ?? [])
      .map(blockToText)
      .filter(Boolean)
      .join('\n')
  }

  return ''
}

const blocksToPlainText = (blocks = []) =>
  blocks
    .map(blockToText)
    .filter(Boolean)
    .join('\n')

const extractApplicability = (text) => {
  const result = {}
  for (const key of ['Tier', 'Product', 'Platform', 'Access Level']) {
    const match = text.match(new RegExp(`${key}:\\s*([^\\n]+)`, 'i'))
    if (match) {
      result[key] = match[1].trim()
    }
  }
  return result
}

const extractGuidePhrase = (text) => {
  const match = text.match(
    /(This guide will cover(?: how to| the following)?|This help article covers(?: the following)?|Table of Contents|Contents?)[:\n]/i,
  )
  return match ? match[1].trim() : null
}

const extractHeadings = (blocks = []) =>
  blocks
    .filter((block) =>
      ['heading', 'subheading', 'subheading3'].includes(block.type),
    )
    .map((block) => ({
      level:
        block.type === 'heading' ? 1 : block.type === 'subheading' ? 2 : 3,
      text: stripHtml(block.text),
    }))

const firstInstructionLeadIns = (blocks = []) =>
  blocks
    .filter((block) => block.type === 'paragraph')
    .map((block) => stripHtml(block.text))
    .filter((text) => /^To\s+\w+/i.test(text))
    .slice(0, 12)

const fetchText = async (url) => {
  const response = await fetch(url, {
    headers: {
      'user-agent':
        'Mozilla/5.0 StaffAnyHelpStyleCrawler/1.0 (+style analysis)',
    },
  })
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  return await response.text()
}

const sitemap = await fetchText(SITEMAP_URL)
const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)]
  .map((match) => decodeXml(match[1]).replace('http://', 'https://'))
  .filter((url) => /\/en\/articles\//.test(url))

const articles = []
const failures = []

for (const [index, url] of urls.entries()) {
  try {
    const html = await fetchText(url)
    const data = extractNextData(html)
    const article = data?.props?.pageProps?.articleContent
    if (!article) {
      throw new Error('Missing articleContent')
    }
    const text = blocksToPlainText(article.blocks ?? [])
    const headings = extractHeadings(article.blocks ?? [])
    articles.push({
      url,
      id: article.articleId ?? article.id,
      title: article.title,
      description: article.description ?? '',
      subtitle: article.description ?? '',
      applicability: extractApplicability(text),
      guidePhrase: extractGuidePhrase(text),
      headingCount: headings.length,
      headings: headings.slice(0, 30),
      instructionLeadIns: firstInstructionLeadIns(article.blocks ?? []),
      hasFaq:
        headings.some((heading) => /\bFAQ\b/i.test(heading.text)) ||
        /\bQ:\s+/i.test(text),
      hasImages: (article.blocks ?? []).some((block) => block.type === 'image'),
      hasTables: (article.blocks ?? []).some((block) => block.type === 'table'),
      textLength: text.length,
      lastUpdated: article.lastUpdatedDate ?? article.lastUpdated ?? null,
    })
  } catch (error) {
    failures.push({ url, error: error.message })
  }

  if ((index + 1) % 25 === 0 || index + 1 === urls.length) {
    console.log(`Crawled ${index + 1}/${urls.length}`)
  }

  if (index + 1 < urls.length) {
    await sleep(DELAY_MS)
  }
}

const countBy = (items, getKey) =>
  items.reduce((acc, item) => {
    const key = getKey(item) || 'Unspecified'
    acc[key] = (acc[key] ?? 0) + 1
    return acc
  }, {})

const titleStarts = countBy(articles, (article) => article.title.split(/\s+/)[0])
const guidePhrases = countBy(articles, (article) => article.guidePhrase)
const platforms = countBy(articles, (article) => article.applicability.Platform)
const products = countBy(articles, (article) => article.applicability.Product)
const accessLevels = countBy(
  articles,
  (article) => article.applicability['Access Level'],
)

const analysis = {
  crawledAt: new Date().toISOString(),
  sitemapUrl: SITEMAP_URL,
  articleCount: articles.length,
  failureCount: failures.length,
  failures,
  summary: {
    titleStarts,
    guidePhrases,
    platforms,
    products,
    accessLevels,
    withFaq: articles.filter((article) => article.hasFaq).length,
    withImages: articles.filter((article) => article.hasImages).length,
    withTables: articles.filter((article) => article.hasTables).length,
    avgHeadingCount:
      articles.reduce((sum, article) => sum + article.headingCount, 0) /
      Math.max(articles.length, 1),
  },
  articles,
}

await fs.writeFile(OUT_PATH, JSON.stringify(analysis, null, 2))
console.log(`Wrote ${OUT_PATH}`)
