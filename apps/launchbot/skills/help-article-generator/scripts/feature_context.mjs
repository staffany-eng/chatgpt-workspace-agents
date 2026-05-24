#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const STOP_WORDS = new Set([
  'a',
  'an',
  'and',
  'app',
  'are',
  'by',
  'for',
  'from',
  'in',
  'into',
  'is',
  'of',
  'on',
  'or',
  'staffany',
  'the',
  'to',
  'web',
  'with',
])

function parseArgs(argv) {
  const args = {
    feature: '',
    max: 80,
    repo: process.env.LAUNCH_PANTHEON_REPO || process.env.PANTHEON_REPO || '',
  }

  const loose = []
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]

    if (arg === '--feature' || arg === '-f') {
      args.feature = argv[i + 1] ?? ''
      i += 1
      continue
    }

    if (arg === '--max' || arg === '-m') {
      const value = Number(argv[i + 1])
      if (Number.isFinite(value) && value > 0) {
        args.max = Math.min(200, Math.max(10, Math.floor(value)))
      }
      i += 1
      continue
    }

    if (arg === '--repo' || arg === '-r') {
      args.repo = argv[i + 1] ?? ''
      i += 1
      continue
    }

    if (arg === '--help' || arg === '-h') {
      printHelp(0)
      process.exit(0)
    }

    if (!arg.startsWith('-')) {
      loose.push(arg)
    }
  }

  if (!args.feature && loose.length > 0) {
    args.feature = loose.join(' ')
  }

  if (!args.feature.trim()) {
    printHelp(1)
    process.exit(1)
  }

  return args
}

function printHelp(exitCode) {
  const stream = exitCode === 0 ? process.stdout : process.stderr
  stream.write(
    [
      'Usage: node feature_context.mjs --feature "<feature name>" [--max 80] [--repo /path/to/pantheon]',
      '',
      'Examples:',
      '  node feature_context.mjs --feature "Timeclock Sidekick"',
      '  node feature_context.mjs --feature "Timeclock Sidekick" --repo /path/to/pantheon',
      '  node feature_context.mjs -f "BPJS calculation pay item" --max 120',
      '',
    ].join('\n'),
  )
}

function hasPath(p) {
  try {
    fs.accessSync(p)
    return true
  } catch {
    return false
  }
}

function findRepoRoot(explicitRepo) {
  if (explicitRepo) {
    const resolved = path.resolve(explicitRepo)
    if (hasPath(path.join(resolved, 'AGENTS.md')) && hasPath(path.join(resolved, 'apps'))) {
      return resolved
    }
    throw new Error(`Could not locate Pantheon repo root at ${resolved} (missing AGENTS.md/apps).`)
  }

  const scriptDir = path.dirname(fileURLToPath(import.meta.url))
  const seeds = [process.cwd(), path.resolve(scriptDir, '../../../../')]

  for (const seed of seeds) {
    let current = path.resolve(seed)
    while (true) {
      if (
        hasPath(path.join(current, 'AGENTS.md')) &&
        hasPath(path.join(current, 'apps'))
      ) {
        return current
      }

      const parent = path.dirname(current)
      if (parent === current) {
        break
      }
      current = parent
    }
  }

  throw new Error('Could not locate Pantheon repo root (missing AGENTS.md/apps).')
}

function escapeRegex(input) {
  return input.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function normalizeFeature(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
}

function featureTokens(text) {
  const normalized = normalizeFeature(text)
  const raw = normalized.split(/\s+/).filter(Boolean)

  const tokens = []
  for (const token of raw) {
    if (token.length < 3) {
      continue
    }
    if (STOP_WORDS.has(token)) {
      continue
    }
    if (!tokens.includes(token)) {
      tokens.push(token)
    }
  }

  return tokens
}

function parseLinkEntries(filePath, source) {
  if (!hasPath(filePath)) {
    return []
  }

  const content = fs.readFileSync(filePath, 'utf8')
  const entries = []
  const regex = /^\s*([A-Z0-9_]+)\s*:\s*'([^']+)'/gm
  let match = regex.exec(content)

  while (match) {
    entries.push({
      source,
      key: match[1],
      url: match[2],
      filePath,
    })
    match = regex.exec(content)
  }

  return entries
}

function scoreLink(entry, phrase, tokens) {
  const haystack = `${entry.key} ${entry.url}`.toLowerCase()
  let score = 0

  if (phrase && haystack.includes(phrase)) {
    score += 8
  }

  for (const token of tokens) {
    if (haystack.includes(token)) {
      score += 2
    }
    if (entry.key.toLowerCase().includes(token)) {
      score += 1
    }
  }

  return score
}

function rgSearch(root, pattern, paths, limit) {
  const existingPaths = paths.filter((p) => hasPath(path.join(root, p)))
  if (existingPaths.length === 0) {
    return []
  }

  const args = [
    '-n',
    '-i',
    '--no-heading',
    '--color',
    'never',
    '-e',
    pattern,
    ...existingPaths,
  ]

  const result = spawnSync('rg', args, {
    cwd: root,
    encoding: 'utf8',
  })

  if (result.error) {
    throw result.error
  }

  if (result.status === 1) {
    return []
  }

  if (result.status !== 0) {
    const stderr = result.stderr?.trim()
    throw new Error(stderr || `rg exited with status ${result.status}`)
  }

  const lines = result.stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  return dedupe(lines).slice(0, limit)
}

function dedupe(items) {
  return [...new Set(items)]
}

function compactMatch(line) {
  const first = line.indexOf(':')
  const second = line.indexOf(':', first + 1)

  if (first === -1 || second === -1) {
    return line
  }

  const file = line.slice(0, first)
  const row = line.slice(first + 1, second)
  const snippet = line
    .slice(second + 1)
    .trim()
    .replace(/\s+/g, ' ')
    .slice(0, 180)

  return `${file}:${row} - ${snippet}`
}

function section(title, lines) {
  if (lines.length === 0) {
    return `## ${title}\n\n- No direct matches found.\n`
  }

  const items = lines.map((line) => `- ${compactMatch(line)}`).join('\n')
  return `## ${title}\n\n${items}\n`
}

function formatLinks(links) {
  if (links.length === 0) {
    return '## Existing Help Center Links\n\n- No close link matches found in code constants.\n'
  }

  const header = [
    '## Existing Help Center Links',
    '',
    '| Source | Key | URL |',
    '| --- | --- | --- |',
  ]

  const rows = links.map(
    (entry) => `| ${entry.source} | ${entry.key} | ${entry.url} |`,
  )

  return `${header.concat(rows).join('\n')}\n`
}

function topFiles(sections, max = 12) {
  const files = []

  for (const lines of sections) {
    for (const line of lines) {
      const idx = line.indexOf(':')
      if (idx > 0) {
        const file = line.slice(0, idx)
        if (!files.includes(file)) {
          files.push(file)
        }
      }
    }
  }

  return files.slice(0, max)
}

function main() {
  const args = parseArgs(process.argv.slice(2))
  const root = findRepoRoot(args.repo)
  const phrase = normalizeFeature(args.feature)
  const tokens = featureTokens(args.feature)

  const gryphonLinks = parseLinkEntries(
    path.join(root, 'apps/gryphon/src/common/data/knowledgeBaseLinks.ts'),
    'gryphon',
  )
  const pixieLinks = parseLinkEntries(
    path.join(root, 'apps/pixie/src/common/data/IntercomArticleLinks.ts'),
    'pixie',
  )

  const candidateLinks = [...gryphonLinks, ...pixieLinks]
    .map((entry) => ({
      ...entry,
      score: scoreLink(entry, phrase, tokens),
    }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 15)

  const searchPattern = [escapeRegex(args.feature.trim()), ...tokens.map(escapeRegex)]
    .filter(Boolean)
    .join('|')

  const webRefs = rgSearch(
    root,
    searchPattern,
    [
      'apps/gryphon/src/main/settings',
      'apps/gryphon/src/main/payroll',
      'apps/gryphon/src/main/leave',
      'apps/gryphon/src/components',
      'apps/gryphon/src/common/data/knowledgeBaseLinks.ts',
    ],
    args.max,
  )

  const mobileRefs = rgSearch(
    root,
    searchPattern,
    [
      'apps/pixie/src/profile/settings',
      'apps/pixie/src/profile',
      'apps/pixie/src/onBoarding',
      'apps/pixie/src/common/data/IntercomArticleLinks.ts',
    ],
    args.max,
  )

  const backendRefs = rgSearch(
    root,
    searchPattern,
    ['apps/kraken/src/server'],
    args.max,
  )

  const gryphonLinkKeys = candidateLinks
    .filter((entry) => entry.source === 'gryphon')
    .map((entry) => entry.key)
    .slice(0, 12)

  const pixieLinkKeys = candidateLinks
    .filter((entry) => entry.source === 'pixie')
    .map((entry) => entry.key)
    .slice(0, 12)

  const gryphonHelpRefPattern =
    gryphonLinkKeys.length > 0
      ? `KNOWLEDGE_BASE_LINKS\\.(${gryphonLinkKeys.map(escapeRegex).join('|')})`
      : ''
  const pixieHelpRefPattern =
    pixieLinkKeys.length > 0
      ? `IntercomArticleLinks\\.(${pixieLinkKeys.map(escapeRegex).join('|')})|INTERCOM_ARTICLE_LINKS\\.(${pixieLinkKeys.map(escapeRegex).join('|')})`
      : ''

  const helpRefs = []
  if (gryphonHelpRefPattern) {
    helpRefs.push(
      ...rgSearch(root, gryphonHelpRefPattern, ['apps/gryphon/src'], args.max),
    )
  }
  if (pixieHelpRefPattern) {
    helpRefs.push(
      ...rgSearch(root, pixieHelpRefPattern, ['apps/pixie/src'], args.max),
    )
  }

  const deepDiveFiles = topFiles([webRefs, mobileRefs, backendRefs, helpRefs], 12)

  const output = [
    '# Help Article Context Pack',
    '',
    `- Generated: ${new Date().toISOString()}`,
    `- Repository: ${root}`,
    `- Feature Query: ${args.feature}`,
    `- Search Tokens: ${tokens.length > 0 ? tokens.join(', ') : '(none)'}`,
    '',
    formatLinks(candidateLinks),
    section('Web Settings References (Gryphon)', webRefs),
    section('Mobile References (Pixie)', mobileRefs),
    section('Backend References (Kraken)', backendRefs),
    section('Help-Link Usage References', dedupe(helpRefs).slice(0, args.max)),
    '## Suggested Files To Open First',
    '',
    ...(deepDiveFiles.length > 0
      ? deepDiveFiles.map((file, i) => `${i + 1}. ${file}`)
      : ['1. No specific files found; broaden feature query keywords.']),
    '',
    '## Drafting Notes',
    '',
    '- Use exact UI labels/options from evidence lines when available.',
    '- If values/defaults are unclear, mark them under assumptions instead of asserting.',
    '- Keep setup steps in click-path order, then add a settings table and troubleshooting.',
    '',
  ]

  process.stdout.write(output.join('\n'))
}

main()
