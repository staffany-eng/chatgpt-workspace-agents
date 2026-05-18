#!/usr/bin/env node

import fs from 'node:fs'
import { loadLocalEnvFile } from './load-env.mjs'

const NOTION_API = 'https://api.notion.com/v1'
const NOTION_VERSION = '2022-06-28'

function fail(message) {
  console.error(`Error: ${message}`)
  process.exit(1)
}

function parseArgs(argv) {
  const parsed = {
    page: '',
    database: '',
    parentPage: '',
    templatePage: '',
    targetRelease: '',
    dri: '',
    title: '',
    filePath: '',
    mode: 'replace',
    dryRun: false,
    help: false,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--help' || arg === '-h') parsed.help = true
    else if (arg === '--page') parsed.page = argv[++i] ?? ''
    else if (arg === '--database') parsed.database = argv[++i] ?? ''
    else if (arg === '--parent-page') parsed.parentPage = argv[++i] ?? ''
    else if (arg === '--template-page') parsed.templatePage = argv[++i] ?? ''
    else if (arg === '--target-release') parsed.targetRelease = argv[++i] ?? ''
    else if (arg === '--dri') parsed.dri = argv[++i] ?? ''
    else if (arg === '--title') parsed.title = argv[++i] ?? ''
    else if (arg === '--file') parsed.filePath = argv[++i] ?? ''
    else if (arg === '--mode') parsed.mode = argv[++i] ?? ''
    else if (arg === '--dry-run') parsed.dryRun = true
  }

  return parsed
}

function printUsage() {
  console.log(`Usage:
  node scripts/sync-prd-notion.mjs --file <PRD_MD> [--page <PAGE_ID|URL> | --database <DB_ID|URL> | --parent-page <PAGE_ID|URL>] [options]

Options:
  --page <ID|URL>         Update an existing Notion page
  --database <ID|URL>     Create a new page in this database when --page is not provided
  --parent-page <ID|URL>  Create a new page under this parent page when --database is not provided
  --template-page <ID|URL> Template page to duplicate when creating in database
  --target-release <TEXT>  Explicit release value (e.g. 26Q2, S26052). Not auto-filled by default
  --dri <TEXT>             Explicit DRI name. Defaults to blank
  --title <TEXT>          New page title (default: first markdown H1 or filename)
  --mode <MODE>           replace | append (default: replace)
  --dry-run               Print plan only
  -h, --help              Show help

Env:
  NOTION_API_TOKEN        Required Notion integration token
`)
}

function normalizeNotionId(value) {
  const trimmed = String(value || '').trim()
  if (!trimmed) return ''

  const urlMatch = trimmed.match(/([a-f0-9]{32})(?:\?|$)/iu)
  if (urlMatch) return urlMatch[1].toLowerCase()

  const hyphenMatch = trimmed.match(
    /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/iu,
  )
  if (hyphenMatch) return hyphenMatch[0].replace(/-/gu, '').toLowerCase()

  const plainMatch = trimmed.match(/^[a-f0-9]{32}$/iu)
  return plainMatch ? plainMatch[0].toLowerCase() : ''
}

function withHyphens(id32) {
  return `${id32.slice(0, 8)}-${id32.slice(8, 12)}-${id32.slice(12, 16)}-${id32.slice(16, 20)}-${id32.slice(20)}`
}

function titleFromMarkdown(markdown, fallback) {
  const m = markdown.match(/^#\s+(.+)$/mu)
  return m?.[1]?.trim() || fallback
}

function normalizePrdTitle(rawTitle, fallbackTitle = 'PRD', filePath = '') {
  const raw = String(rawTitle || '').trim()
  const fallback = String(fallbackTitle || 'PRD').trim() || 'PRD'
  const source = raw || fallback

  const fromFileDate = String(filePath || '').match(/(20\d{2})-(\d{2})-(\d{2})/)
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const defaultDate = `${y}${m}${d}`
  const datePrefix = fromFileDate
    ? `${fromFileDate[1]}${fromFileDate[2]}${fromFileDate[3]}`
    : defaultDate

  const toReadableCore = (value) =>
    String(value || '')
      .replace(/^product requirements document\s*[-:]\s*/iu, '')
      .replace(/^product requirements document\s*/iu, '')
      .replace(/^20\d{2}-\d{2}-\d{2}[-_\s]*/u, '')
      .replace(/^\d{8}\s*-\s*/u, '')
      .replace(/\bprd\b$/iu, '')
      .replace(/[-_]?prd$/iu, '')
      .replace(/\s*\(prd\)\s*$/iu, '')
      .replace(/[_-]+/gu, ' ')
      .replace(/\s+/gu, ' ')
      .trim()
      .replace(/\b\w/gu, (c) => c.toUpperCase())

  let core = toReadableCore(source)
  if (!core) core = toReadableCore(fallback)
  if (!core) core = 'PRD'
  return `${datePrefix} - ${core} (PRD)`
}

function richText(text) {
  return [{ type: 'text', text: { content: text } }]
}

function chunk(items, size) {
  const out = []
  for (let i = 0; i < items.length; i += size)
    out.push(items.slice(i, i + size))
  return out
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function normalizeKey(input) {
  return String(input || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/gu, ' ')
    .trim()
}

function parseMarkdownSections(markdown) {
  const lines = markdown.split(/\r?\n/u)
  const sections = new Map()
  let current = ''
  let buf = []

  const flush = () => {
    if (!current) return
    sections.set(current, buf.join('\n').trim())
  }

  for (const line of lines) {
    const m = line.match(/^##\s+(.+)$/u)
    if (m) {
      flush()
      current = m[1].trim()
      buf = []
      continue
    }
    if (current) buf.push(line)
  }
  flush()
  return sections
}

function firstMarkdownTableRows(fragment) {
  const lines = String(fragment || '').split(/\r?\n/u)
  let i = 0
  while (i < lines.length) {
    if (
      lines[i].includes('|') &&
      i + 1 < lines.length &&
      /^\s*\|?[\s:-]+(\|[\s:-]+)+\|?\s*$/u.test(lines[i + 1])
    ) {
      const rows = []
      while (i < lines.length && lines[i].includes('|')) {
        const row = lines[i].trim().replace(/^\|/u, '').replace(/\|$/u, '')
        rows.push(row.split('|').map((c) => c.trim()))
        i += 1
      }
      return rows
    }
    i += 1
  }
  return []
}

function isSeparatorRow(row) {
  return row.every((cell) => /^:?-{2,}:?$/u.test(String(cell || '').trim()))
}

function stripMarkdown(text) {
  return String(text || '')
    .replace(/\*\*/gu, '')
    .replace(/`/gu, '')
    .trim()
}

function normalizeAcceptanceCriteriaText(raw) {
  let text = stripMarkdown(raw)
  if (!text) return ''

  text = text
    .replace(/\s+(\d+)\)/gu, '\n$1. ')
    .replace(/^(\d+)\)\s*/u, '$1. ')
    .replace(/\s+([a-z])\)/giu, '\n  $1. ')
    .replace(/\s+([ivxlcdm]+)\)/giu, '\n    $1. ')

  return text
    .split(/\n+/u)
    .map((s) => s.trimEnd())
    .filter(Boolean)
    .join('\n')
}

function compactCellTextByHeader(header, raw) {
  const key = normalizeKey(header)
  const value = stripMarkdown(raw)
  if (!value) return ''

  if (key === '#no' || key === 'no') return value.split(/\s+/u)[0]
  if (key === '#sr' || key === 'sr') return value.replace(/\s+/gu, '')
  if (key === 'acceptance criteria')
    return normalizeAcceptanceCriteriaText(value)
  if (key === 'priority') return value.split(/\s+/u)[0]
  return value
}

function normalizeGoalsText(raw) {
  const text = stripMarkdown(raw)
  if (!text) return ''
  const pieces = text
    .replace(/\s+(\d+\))/gu, '\n$1')
    .split(/\n+/u)
    .map((s) => s.trim())
    .filter(Boolean)

  if (pieces.length > 1) {
    return pieces.join('\n')
  }

  const fallback = text
    .replace(/\s+(\d+\.)\s+/gu, '\n$1 ')
    .split(/\n+/u)
    .map((s) => s.trim())
    .filter(Boolean)

  return fallback.join('\n')
}

function normalizeBulletLines(raw) {
  const text = stripMarkdown(raw)
  if (!text) return ''
  return text
    .replace(/\s+-\s+/gu, '\n- ')
    .split(/\n+/u)
    .map((s) => s.trim())
    .filter(Boolean)
    .join('\n')
}

function parsePrdPropertyValues(
  markdown,
  fallbackTitle,
  { explicitTargetRelease = '', explicitDri = '' } = {},
) {
  const sections = parseMarkdownSections(markdown)
  const overviewRows = firstMarkdownTableRows(sections.get('Overview') || '')

  const overviewMap = new Map()
  const overviewDataRows = overviewRows
    .slice(1)
    .filter((row) => !isSeparatorRow(row))
  for (const row of overviewDataRows) {
    const key = normalizeKey(stripMarkdown(row[0] || ''))
    const value = stripMarkdown(row[1] || '')
    if (key) overviewMap.set(key, value)
  }

  const title = normalizePrdTitle(
    titleFromMarkdown(markdown, fallbackTitle),
    fallbackTitle,
    '',
  )
  const tags = []
  if (/manual overtime/iu.test(title)) tags.push('Manual Overtime')
  tags.push('PRD')

  return {
    targetRelease: stripMarkdown(explicitTargetRelease || ''),
    tags,
    dri: stripMarkdown(explicitDri || ''),
    goals: normalizeGoalsText(overviewMap.get('goals') || ''),
    background: overviewMap.get('background and strategic fit') || '',
    scope: normalizeBulletLines(overviewMap.get('scope') || ''),
    outOfScope: normalizeBulletLines(overviewMap.get('out of scope') || ''),
    assumption: normalizeBulletLines(overviewMap.get('assumptions') || ''),
  }
}

function markdownToNotionBlocks(markdown) {
  const lines = markdown.split(/\r?\n/u)
  const blocks = []

  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      i += 1
      continue
    }

    const h1 = trimmed.match(/^#\s+(.+)$/u)
    if (h1) {
      i += 1
      continue
    }

    const h2 = trimmed.match(/^##\s+(.+)$/u)
    if (h2) {
      blocks.push({
        type: 'heading_2',
        heading_2: { rich_text: richText(h2[1]) },
      })
      i += 1
      continue
    }

    const h3 = trimmed.match(/^###\s+(.+)$/u)
    if (h3) {
      blocks.push({
        type: 'heading_3',
        heading_3: { rich_text: richText(h3[1]) },
      })
      i += 1
      continue
    }

    const bullet = trimmed.match(/^[-*]\s+(.+)$/u)
    if (bullet) {
      blocks.push({
        type: 'bulleted_list_item',
        bulleted_list_item: { rich_text: richText(bullet[1]) },
      })
      i += 1
      continue
    }

    const ordered = trimmed.match(/^\d+\.\s+(.+)$/u)
    if (ordered) {
      blocks.push({
        type: 'numbered_list_item',
        numbered_list_item: { rich_text: richText(ordered[1]) },
      })
      i += 1
      continue
    }

    if (
      trimmed.includes('|') &&
      i + 1 < lines.length &&
      /^\s*\|?\s*[:\-]/u.test(lines[i + 1].trim())
    ) {
      const tableRows = []
      while (i < lines.length && lines[i].includes('|')) {
        const row = lines[i].trim().replace(/^\|/u, '').replace(/\|$/u, '')
        tableRows.push(row.split('|').map((c) => c.trim()))
        i += 1
      }
      if (tableRows.length > 1) {
        const withoutSeparators = tableRows.filter(
          (row, idx) => idx === 0 || !isSeparatorRow(row),
        )
        const headers = withoutSeparators[0] || []
        const width = headers.length || 1
        const rowBlocks = withoutSeparators.map((row) => ({
          object: 'block',
          type: 'table_row',
          table_row: {
            cells: Array.from({ length: width }).map((_, idx) => {
              const header = headers[idx] || ''
              const cell = compactCellTextByHeader(header, row[idx] || '')
              return richText(cell)
            }),
          },
        }))
        blocks.push({
          type: 'table',
          table: {
            table_width: width,
            has_column_header: true,
            has_row_header: false,
            children: rowBlocks,
          },
        })
      }
      continue
    }

    blocks.push({
      type: 'paragraph',
      paragraph: { rich_text: richText(trimmed) },
    })
    i += 1
  }

  return blocks
}

function buildNotionBodyMarkdown(markdown) {
  const sections = parseMarkdownSections(markdown)
  const includeOrder = [
    'Current UX Baseline (Mandatory When UX Scope Exists)',
    'Risks',
    'Open Questions',
    'Reference Links Used for Benchmarking',
    'Affected Files (Predicted)',
  ]

  const chunks = []
  for (const heading of includeOrder) {
    const body = sections.get(heading)
    if (!body) continue
    chunks.push(`## ${heading}\n\n${body}`.trim())
  }

  return chunks.join('\n\n')
}

function parseRequirementsRows(markdown) {
  const sections = parseMarkdownSections(markdown)
  const req = sections.get('Requirements') || ''
  const rows = firstMarkdownTableRows(req)
  if (rows.length < 2) return []
  const dataRows = rows.slice(1).filter((row) => !isSeparatorRow(row))
  const parsed = dataRows.map((row) => ({
    no: stripMarkdown(row[0] || ''),
    userStory: stripMarkdown(row[1] || ''),
    sr: stripMarkdown(row[2] || ''),
    requirement: stripMarkdown(row[3] || ''),
    acceptanceCriteria: normalizeAcceptanceCriteriaText(row[4] || ''),
    priority: stripMarkdown(row[5] || ''),
    engUnit: stripMarkdown(row[6] || ''),
  }))

  const firstExplicitStory =
    parsed.find((row) => row.userStory)?.userStory || ''
  const defaultStory =
    firstExplicitStory ||
    'As a manager/owner, I want to manage manual overtime with clear controls, so that payroll remains accurate, timely, and auditable.'

  for (const row of parsed) {
    if (!row.userStory) row.userStory = defaultStory
  }
  return parsed
}

function requirementCodeSortKey(row) {
  const code = String(row?.sr || row?.no || '').trim()
  const m = code.match(/^([A-Za-z]+)-?(\d+)$/u)
  if (!m) return { prefix: 'ZZZ', number: Number.MAX_SAFE_INTEGER, raw: code }
  return {
    prefix: m[1].toUpperCase(),
    number: Number.parseInt(m[2], 10),
    raw: code,
  }
}

function compareRequirementsByCodeAsc(a, b) {
  const ka = requirementCodeSortKey(a)
  const kb = requirementCodeSortKey(b)
  if (ka.prefix !== kb.prefix) return ka.prefix.localeCompare(kb.prefix)
  if (ka.number !== kb.number) return ka.number - kb.number
  return ka.raw.localeCompare(kb.raw)
}

function normalizePriorityValue(input) {
  const raw = String(input || '')
    .trim()
    .toUpperCase()
  if (raw === 'MVP' || raw === 'P1' || raw === 'P2') return raw
  if (raw === 'HIGH') return 'MVP'
  if (raw === 'MEDIUM') return 'P1'
  if (raw === 'LOW') return 'P2'
  return ''
}

async function findRequirementsDatabaseId({ token, pageId }) {
  const children = await listBlockChildren(pageId, token)
  const byTitle = children.find(
    (b) =>
      b?.type === 'child_database' &&
      normalizeKey(b?.child_database?.title || '').includes('requirements'),
  )
  if (byTitle?.id) return normalizeNotionId(byTitle.id)
  const linkedDb = children.find(
    (b) =>
      b?.type === 'link_to_page' &&
      b?.link_to_page?.type === 'database_id' &&
      typeof b?.link_to_page?.database_id === 'string',
  )
  if (linkedDb?.link_to_page?.database_id) {
    return normalizeNotionId(linkedDb.link_to_page.database_id)
  }
  const anyChildDb = children.find((b) => b?.type === 'child_database')
  if (anyChildDb?.id) return normalizeNotionId(anyChildDb.id)
  return ''
}

async function findRequirementsSourceDatabaseId({
  token,
  parentPageId,
  targetPageId,
}) {
  const children = await listBlockChildren(parentPageId, token)
  const expectedTitle = normalizeKey(`Technical Requirements`)
  const match = children.find(
    (b) =>
      b?.type === 'child_database' &&
      normalizeKey(b?.child_database?.title || '') === expectedTitle,
  )
  return match?.id ? normalizeNotionId(match.id) : ''
}

async function createRequirementsSourceDatabase({
  token,
  parentPageId,
  targetPageId,
}) {
  const body = {
    parent: { page_id: withHyphens(parentPageId) },
    title: [
      {
        type: 'text',
        text: { content: `Requirements List` },
      },
    ],
    properties: {
      Name: { title: {} },
      Code: { rich_text: {} },
      Priority: {
        select: {
          options: [
            { name: 'MVP', color: 'red' },
            { name: 'P1', color: 'yellow' },
            { name: 'P2', color: 'green' },
          ],
        },
      },
      Notes: { rich_text: {} },
    },
  }
  const db = await notionRequest({
    method: 'POST',
    path: '/databases',
    token,
    body,
  })
  const id = normalizeNotionId(db?.id || '')
  if (!id) throw new Error('Failed to create Requirements source database.')
  return id
}

async function queryDatabasePages(databaseId, token) {
  const results = []
  let cursor = ''
  while (true) {
    const body = cursor
      ? { start_cursor: cursor, page_size: 100 }
      : { page_size: 100 }
    const data = await notionRequest({
      method: 'POST',
      path: `/databases/${withHyphens(databaseId)}/query`,
      token,
      body,
    })
    results.push(...(data.results || []))
    if (!data.has_more) break
    cursor = data.next_cursor
  }
  return results
}

async function clearRequirementsDatabaseItems({ databaseId, token }) {
  const pages = await queryDatabasePages(databaseId, token)
  for (const page of pages) {
    if (!page?.id) continue
    await notionRequest({
      method: 'PATCH',
      path: `/pages/${page.id}`,
      token,
      body: { archived: true },
    })
  }
}

function buildAcceptanceCriteriaBlocks(acText) {
  const lines = String(acText || '')
    .split(/\n+/u)
    .map((s) => s.trim())
    .filter(Boolean)
  const blocks = []
  for (const line of lines) {
    const top = line.match(/^(\d+)\.\s+(.+)$/u)
    const sub = line.match(/^([a-z]+)\.\s+(.+)$/iu)
    if (top) {
      blocks.push({
        type: 'numbered_list_item',
        numbered_list_item: { rich_text: richText(top[2]) },
      })
    } else if (sub) {
      blocks.push({
        type: 'bulleted_list_item',
        bulleted_list_item: { rich_text: richText(`${sub[1]}. ${sub[2]}`) },
      })
    } else {
      blocks.push({
        type: 'paragraph',
        paragraph: { rich_text: richText(line) },
      })
    }
  }
  return blocks
}

async function createRequirementItem({ token, databaseId, row }) {
  const title = row.requirement || row.sr || 'Requirement'
  const quickNotes = row.userStory || row.requirement || ''
  const priority = normalizePriorityValue(row.priority)
  const body = {
    parent: { database_id: withHyphens(databaseId) },
    properties: {
      Name: { title: richText(title) },
      Code: { rich_text: richText(row.sr || row.no || '') },
      Priority: { select: priority ? { name: priority } : null },
      Notes: { rich_text: richText(quickNotes) },
    },
    children: [
      { type: 'heading_2', heading_2: { rich_text: richText('User Story') } },
      {
        type: 'paragraph',
        paragraph: { rich_text: richText(row.userStory || '') },
      },
      {
        type: 'heading_2',
        heading_2: { rich_text: richText('Acceptance Criteria') },
      },
      ...buildAcceptanceCriteriaBlocks(row.acceptanceCriteria),
    ],
  }
  await notionRequest({ method: 'POST', path: '/pages', token, body })
}

async function enforceRequirementsPrioritySchema({ token, databaseId }) {
  await notionRequest({
    method: 'PATCH',
    path: `/databases/${withHyphens(databaseId)}`,
    token,
    notionVersion: '2026-03-11',
    body: {
      properties: {
        Priority: {
          select: {
            options: [
              { name: 'MVP', color: 'red' },
              { name: 'P1', color: 'yellow' },
              { name: 'P2', color: 'green' },
            ],
          },
        },
      },
    },
  })
}

async function listDatabaseViews(databaseId, token) {
  const data = await notionRequest({
    method: 'GET',
    path: `/views?database_id=${encodeURIComponent(withHyphens(databaseId))}`,
    token,
    notionVersion: '2026-03-11',
  })
  return data?.results || []
}

async function createRequirementsInlineView({
  token,
  pageId,
  afterBlockId,
  sourceDatabaseId,
}) {
  const sourceDatabase = await getDatabase(sourceDatabaseId, token)
  const dataSourceId = sourceDatabase?.data_sources?.[0]?.id
  if (!dataSourceId) {
    throw new Error('Requirements source database has no data source id.')
  }

  const view = await notionRequest({
    method: 'POST',
    path: '/views',
    token,
    notionVersion: '2026-03-11',
    body: {
      create_database: {
        parent: {
          type: 'page_id',
          page_id: withHyphens(pageId),
        },
        position: {
          type: 'after_block',
          block_id: withHyphens(afterBlockId),
        },
      },
      data_source_id: dataSourceId,
      name: 'Requirements',
      type: 'table',
      configuration: {
        type: 'table',
        properties: [
          { property_id: 'Code', visible: true, width: 120 },
          { property_id: 'Name', visible: true, width: 320 },
          { property_id: 'Priority', visible: true, width: 140 },
          { property_id: 'Notes', visible: true, width: 420 },
        ],
        wrap_cells: true,
        frozen_column_index: 1,
        show_vertical_lines: true,
      },
    },
  })

  const linkedDatabaseId = normalizeNotionId(view?.parent?.database_id || '')
  if (!linkedDatabaseId) {
    throw new Error('Failed to create inline Requirements database view.')
  }
  return linkedDatabaseId
}

async function configureRequirementsDatabaseView({ token, databaseId }) {
  const desiredColumns = [
    { property_id: 'Code', visible: true, width: 120 },
    { property_id: 'Name', visible: true, width: 320 },
    { property_id: 'Priority', visible: true, width: 140 },
    { property_id: 'Notes', visible: true, width: 420 },
  ]

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const views = await listDatabaseViews(databaseId, token)
    const viewId = views[0]?.id
    if (!viewId) {
      await sleep(250)
      continue
    }

    await notionRequest({
      method: 'PATCH',
      path: `/views/${viewId}`,
      token,
      notionVersion: '2026-03-11',
      body: {
        name: 'Requirements',
        sorts: [
          {
            property: 'Code',
            direction: 'ascending',
          },
        ],
        configuration: {
          type: 'table',
          properties: desiredColumns,
          wrap_cells: true,
          frozen_column_index: 1,
          show_vertical_lines: true,
        },
      },
    })

    const updatedView = await notionRequest({
      method: 'GET',
      path: `/views/${viewId}`,
      token,
      notionVersion: '2026-03-11',
    })
    const visibleNames = new Set(
      (updatedView?.configuration?.properties || [])
        .filter((prop) => prop?.visible)
        .map((prop) =>
          normalizeKey(prop?.property_name || prop?.property_id || ''),
        ),
    )
    if (
      ['code', 'name', 'priority', 'notes'].every((key) =>
        visibleNames.has(key),
      )
    ) {
      return
    }
    await sleep(250)
  }
}

async function syncRequirementsDatabase({
  token,
  pageId,
  markdown,
  requirementsHeadingBlockId,
  storageParentPageId,
}) {
  const rows = parseRequirementsRows(markdown).sort(
    compareRequirementsByCodeAsc,
  )
  if (rows.length === 0) return
  let dbId = await findRequirementsDatabaseId({ token, pageId })
  if (!dbId) {
    if (!requirementsHeadingBlockId) {
      throw new Error(
        'Requirements heading block is required to create inline Requirements table.',
      )
    }
    if (!storageParentPageId) {
      throw new Error(
        'Missing storage parent page for Requirements source database.',
      )
    }
    console.error(
      '[warn] Requirements DB not found on PRD page. Creating linked inline Requirements table.',
    )
    let sourceDbId = await findRequirementsSourceDatabaseId({
      token,
      parentPageId: storageParentPageId,
      targetPageId: pageId,
    })
    if (!sourceDbId) {
      sourceDbId = await createRequirementsSourceDatabase({
        token,
        parentPageId: storageParentPageId,
        targetPageId: pageId,
      })
    }
    dbId = await createRequirementsInlineView({
      token,
      pageId,
      afterBlockId: requirementsHeadingBlockId,
      sourceDatabaseId: sourceDbId,
    })
  }
  await enforceRequirementsPrioritySchema({ token, databaseId: dbId })
  await configureRequirementsDatabaseView({ token, databaseId: dbId })
  await clearRequirementsDatabaseItems({ databaseId: dbId, token })
  for (const row of [...rows].reverse()) {
    await createRequirementItem({ token, databaseId: dbId, row })
  }
}

async function notionRequest({
  method,
  path,
  token,
  body,
  notionVersion = NOTION_VERSION,
}) {
  const res = await fetch(`${NOTION_API}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'Notion-Version': notionVersion,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${method} ${path} failed (${res.status}): ${text}`)
  }

  if (res.status === 204) return null
  return res.json()
}

async function getPage(pageId, token) {
  return notionRequest({ method: 'GET', path: `/pages/${pageId}`, token })
}

async function getDatabase(databaseId, token) {
  return notionRequest({
    method: 'GET',
    path: `/databases/${withHyphens(databaseId)}`,
    token,
    notionVersion: '2026-03-11',
  })
}

function buildPropertyPatchValue(prop, value) {
  if (value == null) return null
  const textValue = String(value).trim()
  if (prop.type === 'rich_text') {
    return { rich_text: textValue ? richText(textValue) : [] }
  }
  if (prop.type === 'title') {
    return { title: textValue ? richText(textValue) : [] }
  }
  if (prop.type === 'select') {
    return { select: textValue ? { name: textValue } : null }
  }
  if (prop.type === 'multi_select') {
    const arr = Array.isArray(value)
      ? value
      : textValue
        ? textValue.split(',').map((s) => s.trim())
        : []
    return { multi_select: arr.filter(Boolean).map((name) => ({ name })) }
  }
  return null
}

async function patchPrdProperties({ pageId, token, parsed, explicitTitle }) {
  const page = await getPage(pageId, token)
  const properties = page?.properties || {}
  const byNormalized = new Map()
  for (const [name, prop] of Object.entries(properties)) {
    byNormalized.set(normalizeKey(name), { name, prop })
  }

  const mappings = [
    {
      keys: ['target release', 'target releases'],
      value: parsed.targetRelease,
    },
    { keys: ['tags', 'tag'], value: parsed.tags },
    { keys: ['dri'], value: parsed.dri },
    { keys: ['goals', 'goal'], value: parsed.goals },
    {
      keys: [
        'background and strategic fit',
        'background strategic fit',
        'background',
      ],
      value: parsed.background,
    },
    { keys: ['scope'], value: parsed.scope },
    { keys: ['out of scope'], value: parsed.outOfScope },
    { keys: ['assumption', 'assumptions'], value: parsed.assumption },
  ]

  const patch = {}
  for (const entry of mappings) {
    const found = entry.keys
      .map((k) => byNormalized.get(normalizeKey(k)))
      .find(Boolean)
    if (!found) continue
    const payload = buildPropertyPatchValue(found.prop, entry.value)
    if (payload) patch[found.name] = payload
  }

  if (explicitTitle) {
    const titleProp = Object.entries(properties).find(
      ([, p]) => p?.type === 'title',
    )
    if (titleProp) {
      const [name, prop] = titleProp
      const payload = buildPropertyPatchValue(prop, explicitTitle)
      if (payload) patch[name] = payload
    }
  }

  if (Object.keys(patch).length === 0) return
  await notionRequest({
    method: 'PATCH',
    path: `/pages/${pageId}`,
    token,
    body: { properties: patch },
  })
}

async function listBlockChildren(blockId, token) {
  const out = []
  let cursor = ''
  while (true) {
    const q = cursor ? `?start_cursor=${encodeURIComponent(cursor)}` : ''
    const data = await notionRequest({
      method: 'GET',
      path: `/blocks/${blockId}/children${q}`,
      token,
    })
    out.push(...(data.results || []))
    if (!data.has_more) break
    cursor = data.next_cursor
  }
  return out
}

async function clearPageChildren(pageId, token, options = {}) {
  const preserveRequirementDb = Boolean(options.preserveRequirementDb)
  const children = await listBlockChildren(pageId, token)
  for (const child of children) {
    if (preserveRequirementDb) {
      if (child?.type === 'child_database') continue
      if (
        child?.type === 'link_to_page' &&
        child?.link_to_page?.type === 'database_id'
      )
        continue
    }
    await notionRequest({
      method: 'DELETE',
      path: `/blocks/${child.id}`,
      token,
    })
  }
}

async function appendChildren(pageId, token, blocks) {
  const created = []
  const chunks = chunk(blocks, 90)
  for (const part of chunks) {
    const data = await notionRequest({
      method: 'PATCH',
      path: `/blocks/${pageId}/children`,
      token,
      body: { children: part },
    })
    created.push(...(data?.results || []))
  }
  return created
}

async function createPage({
  token,
  databaseId,
  parentPageId,
  templatePageId,
  title,
  blocks,
}) {
  let parent
  const titleProp = { title: [{ type: 'text', text: { content: title } }] }

  if (databaseId) {
    parent = { database_id: withHyphens(databaseId) }
  } else {
    parent = { page_id: withHyphens(parentPageId) }
  }

  const body = {
    parent,
    properties: databaseId ? { Name: titleProp } : undefined,
    children: blocks.slice(0, 90),
  }
  if (databaseId && templatePageId) {
    body.template = {
      type: 'template_id',
      template_id: withHyphens(templatePageId),
    }
  }

  let created
  try {
    created = await notionRequest({
      method: 'POST',
      path: '/pages',
      token,
      body,
    })
  } catch (error) {
    if (databaseId && templatePageId) {
      const fallbackBody = {
        parent,
        properties: { Name: titleProp },
        children: blocks.slice(0, 90),
      }
      created = await notionRequest({
        method: 'POST',
        path: '/pages',
        token,
        body: fallbackBody,
      })
    } else {
      throw error
    }
  }
  const pageId = normalizeNotionId(created.id)
  if (!pageId) throw new Error('Created page did not return a valid id.')

  if (blocks.length > 90) {
    await appendChildren(pageId, token, blocks.slice(90))
  }

  return pageId
}

async function main() {
  loadLocalEnvFile()
  const args = parseArgs(process.argv.slice(2))
  if (args.help) return printUsage()

  if (!args.filePath) fail('Missing --file')
  if (!fs.existsSync(args.filePath))
    fail(`Markdown file not found: ${args.filePath}`)
  if (!['replace', 'append'].includes(args.mode))
    fail('Invalid --mode. Use replace or append.')

  const token = process.env.NOTION_API_TOKEN?.trim()

  const markdown = fs.readFileSync(args.filePath, 'utf8')
  const fallbackTitle =
    args.filePath.split('/').pop()?.replace(/\.md$/u, '') || 'PRD'
  const title = normalizePrdTitle(
    args.title || titleFromMarkdown(markdown, fallbackTitle),
    fallbackTitle,
    args.filePath,
  )
  const bodyMarkdown = buildNotionBodyMarkdown(markdown)
  const blocks = markdownToNotionBlocks(bodyMarkdown)
  const parsedProperties = parsePrdPropertyValues(markdown, fallbackTitle, {
    explicitTargetRelease: args.targetRelease,
    explicitDri: args.dri,
  })

  const pageId = normalizeNotionId(args.page)
  const databaseId = normalizeNotionId(
    args.database || process.env.NOTION_PRD_DATABASE_ID || '',
  )
  const defaultPageId = normalizeNotionId(
    process.env.NOTION_PRD_DEFAULT_PAGE_URL || '',
  )
  const templatePageId = normalizeNotionId(
    args.templatePage ||
      process.env.NOTION_PRD_TEMPLATE_PAGE_ID ||
      defaultPageId ||
      '',
  )
  const parentPageId = normalizeNotionId(
    args.parentPage ||
      (!databaseId ? process.env.NOTION_PRD_DEFAULT_PAGE_URL || '' : ''),
  )

  if (!pageId && !databaseId && !parentPageId) {
    fail(
      'Provide --page, --database, --parent-page, or NOTION_PRD_DATABASE_ID/NOTION_PRD_DEFAULT_PAGE_URL.',
    )
  }

  if (args.dryRun) {
    console.log(
      JSON.stringify(
        {
          mode: args.mode,
          file: args.filePath,
          title,
          pageId: pageId || null,
          databaseId: databaseId || null,
          parentPageId: parentPageId || null,
          templatePageId: templatePageId || null,
          explicitTargetRelease: args.targetRelease || null,
          explicitDri: args.dri || null,
          blockCount: blocks.length,
          parsedProperties,
        },
        null,
        2,
      ),
    )
    return
  }

  if (!token) fail('Missing NOTION_API_TOKEN in environment.')

  let targetPageId = pageId
  if (!targetPageId) {
    targetPageId = await createPage({
      token,
      databaseId,
      parentPageId,
      templatePageId,
      title,
      blocks: [],
    })
    console.error(`[phase] created notion page: ${targetPageId}`)
  }

  console.error('[phase] updating notion properties')
  await patchPrdProperties({
    pageId: targetPageId,
    token,
    parsed: parsedProperties,
    explicitTitle: title,
  })

  if (args.mode === 'replace') {
    console.error('[phase] clearing notion page content')
    await clearPageChildren(targetPageId, token, {
      preserveRequirementDb: false,
    })
  }

  console.error('[phase] appending requirements heading')
  const requirementsHeadingBlocks = await appendChildren(targetPageId, token, [
    { type: 'heading_2', heading_2: { rich_text: richText('Requirements') } },
  ])
  const requirementsHeadingBlockId = requirementsHeadingBlocks[0]?.id
    ? normalizeNotionId(requirementsHeadingBlocks[0].id)
    : ''

  console.error('[phase] creating requirements database + items')
  await syncRequirementsDatabase({
    token,
    pageId: targetPageId,
    markdown,
    requirementsHeadingBlockId,
    storageParentPageId: templatePageId || parentPageId,
  })

  console.error(`[phase] appending ${blocks.length} remaining block(s)`)
  await appendChildren(targetPageId, token, blocks)

  console.log(
    `Notion PRD sync completed for page ${targetPageId} from ${args.filePath}.`,
  )
  console.log(`Page URL: https://www.notion.so/${targetPageId}`)
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
