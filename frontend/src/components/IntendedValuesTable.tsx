import { useMemo } from 'react'

interface Props {
  changes: Record<string, string>
}

export function IntendedValuesTable({ changes }: Props) {
  const entries = useMemo(
    () => Object.entries(changes).sort(([a], [b]) => a.localeCompare(b)),
    [changes],
  )

  if (entries.length === 0) return null

  return (
    <div className="border rounded bg-gray-50 max-h-48 overflow-y-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-gray-100 z-10">
          <tr className="border-b text-gray-500">
            <th className="py-1 px-2 text-left font-medium">Component ID</th>
            <th className="py-1 px-2 text-left font-medium">Intended Value</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([compId, value]) => (
            <tr key={compId} className="border-b border-gray-100 last:border-0">
              <td className="py-0.5 px-2 font-mono text-gray-600 whitespace-nowrap" title={compId}>
                {compId}
              </td>
              <td className="py-0.5 px-2 font-mono text-gray-900">
                {value || <span className="text-gray-300">&mdash;</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
