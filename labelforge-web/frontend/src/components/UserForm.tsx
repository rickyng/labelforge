import React from 'react'
import { useLabels } from '../context/LabelsContext'

export function UserForm() {
  const {
    editableLabels,
    updateLabel,
  } = useLabels()

  if (editableLabels.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-500 text-sm">
        No labels available.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {editableLabels.map((lbl) => {
        const hasEdit = lbl.new_text !== null && lbl.new_text !== lbl.original_text

        return (
          <div
            key={lbl.id}
            className={`rounded-lg border p-3 space-y-1.5 text-sm ${
              hasEdit ? 'border-green-700 bg-green-900/20' : 'border-gray-700 bg-gray-800/50'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-gray-500 text-xs">
                p.{lbl.page + 1}
              </span>
              <span className="text-gray-300 text-xs font-medium truncate flex-1" title={lbl.original_text}>
                {lbl.original_text || <em className="text-gray-600">empty</em>}
              </span>
              {hasEdit && (
                <span className="text-green-500 text-xs shrink-0">edited</span>
              )}
            </div>
            <input
              type="text"
              placeholder={lbl.original_text || 'Replacement text…'}
              value={lbl.new_text ?? ''}
              onChange={(e) =>
                updateLabel(lbl.id, { new_text: e.target.value === '' ? null : e.target.value })
              }
              onClick={(e) => e.stopPropagation()}
              className="input-field"
            />
          </div>
        )
      })}
    </div>
  )
}
