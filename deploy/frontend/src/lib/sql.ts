export type SqlToken = { text: string; kind: "kw" | "str" | "num" | "plain" };

const KEYWORDS = new Set(
  `select from where join inner left right outer full cross on as and or not in is null like between
  group by order having limit offset distinct union all intersect except asc desc count sum avg min max
  case when then else end exists with`.split(/\s+/)
);

const TOKEN = /('(?:[^']|'')*'|"(?:[^"]|"")*")|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(\s+|[^\sA-Za-z0-9_'"]+)/g;

export function tokenizeSql(sql: string): SqlToken[] {
  const out: SqlToken[] = [];
  for (const m of sql.matchAll(TOKEN)) {
    const [text, str, num, word] = m;
    if (str) out.push({ text, kind: "str" });
    else if (num) out.push({ text, kind: "num" });
    else if (word && KEYWORDS.has(word.toLowerCase())) out.push({ text, kind: "kw" });
    else out.push({ text, kind: "plain" });
  }
  return out;
}

const CLAUSE = /\s+(FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|(?:INNER |LEFT |RIGHT |CROSS )?JOIN|UNION(?: ALL)?|INTERSECT|EXCEPT)\b/gi;

/* Put each major clause on its own line; string literals are left byte-for-byte untouched. */
export function formatSql(sql: string): string {
  return sql
    .split(/('(?:[^']|'')*'|"(?:[^"]|"")*")/)
    .map((part, i) => (i % 2 === 1 ? part : part.replace(/\s+/g, " ").replace(CLAUSE, "\n$1")))
    .join("")
    .trim();
}
