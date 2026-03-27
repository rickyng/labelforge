import React from 'react'
import { useLabels } from '../context/LabelsContext'

interface UserFormProps {
  onFieldBlur?: () => void
}

export function UserForm({ onFieldBlur }: UserFormProps = {}) {
  const { editableLabels, updateLabel } = useLabels()

  if (editableLabels.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-2 text-gray-600">
        <svg className="w-8 h-8 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-sm">No editable fields</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col divide-y divide-gray-200">
      {editableLabels.map((lbl) => {
        const hasEdit = lbl.new_text !== null && lbl.new_text !== lbl.original_text

        return (
          <div key={lbl.id} className="px-4 py-3 space-y-1.5">
            {/* Original label — muted, clearly a label */}
            <div className="flex items-center justify-between gap-2">
              <span
                className="text-[11px] font-medium uppercase tracking-wide text-gray-500 truncate flex-1"
                title={lbl.original_text}
              >
                {lbl.original_text || <em>empty</em>}
              </span>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] text-gray-400 tabular-nums">p.{lbl.page + 1}</span>
                {hasEdit && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-brand-600 uppercase tracking-wide">
                    <span className="w-1.5 h-1.5 rounded-full bg-brand-600" />
                    edited
                  </span>
                )}
              </div>
            </div>
            {/* Input — white text, clearly interactive */}
            <input
              type="text"
              aria-label={`Replacement for: ${lbl.original_text || 'empty'}`}
              placeholder={lbl.original_text || 'Replacement text…'}
              value={lbl.new_text ?? ''}
              onChange={(e) =>
                updateLabel(lbl.id, { new_text: e.target.value === '' ? null : e.target.value })
              }
              onClick={(e) => e.stopPropagation()}
              onBlur={onFieldBlur}
              className={`input-field font-medium ${
                hasEdit
                  ? 'border-brand-500 text-gray-900'
                  : 'text-gray-700'
              }`}
            />
          </div>
        )
      })}
    </div>
  )
}
