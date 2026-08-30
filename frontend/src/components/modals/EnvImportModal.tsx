// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { Modal } from '@/components/ui/Modal'
import { InlineEdit } from '@/components/ui/InlineEdit'
import { mask } from '@/lib/format'
import { useKeylens } from '@/store/keylensStore'

/**
 * `.env` 가져오기 - 파싱된 변수를 표로 보여주고 컬렉션 하나로 일괄 저장한다.
 *
 * 값은 기본적으로 마스킹해 보여준다. .env 는 한 파일에 시크릿이 여러 개라 표를 열어둔
 * 채로 화면을 공유하면 전부 노출되기 때문이다. 더블클릭해 편집에 들어갔을 때만 평문이
 * 보인다.
 */
export function EnvImportModal() {
  const open = useKeylens((s) => s.envImportOpen)
  const rows = useKeylens((s) => s.envImportRows)
  const project = useKeylens((s) => s.envImportProject)
  const busy = useKeylens((s) => s.envImportBusy)
  const close = useKeylens((s) => s.closeEnvImport)
  const patch = useKeylens((s) => s.patchEnvRow)
  const setProject = useKeylens((s) => s.setEnvImportProject)
  const save = useKeylens((s) => s.saveEnvImport)

  const checked = rows.filter((r) => r.checked && r.name.trim()).length
  const canSave = !!project.trim() && checked > 0 && !busy

  return (
    <Modal open={open} onClose={close} title=".env 가져오기" className="w-[720px]">
      <div className="text-[15px] font-bold">.env 가져오기</div>
      <p className="mt-1 text-[12.5px] text-muted">
        {rows.length}개를 찾았어요. 이름이나 값을 <strong className="text-fg-soft">더블클릭</strong>하면
        고칠 수 있어요.
      </p>

      <label className="mt-4 block text-[12px] font-semibold text-muted">
        컬렉션 <span className="text-danger">*</span>
        <input
          value={project}
          onChange={(e) => setProject(e.target.value)}
          list="kl-projects"
          placeholder="예: my-blog"
          className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-fg outline-none focus:border-border-strong"
        />
      </label>

      <div className="mt-3 max-h-[320px] overflow-y-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-[12.5px]">
          <thead className="sticky top-0 bg-panel text-[11px] text-faint-2">
            <tr>
              <th scope="col" className="w-[34px] p-2" />
              <th scope="col" className="p-2 text-left font-semibold">변수명</th>
              <th scope="col" className="p-2 text-left font-semibold">값</th>
              <th scope="col" className="w-[150px] p-2 text-left font-semibold">종류</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              // 이름이 비어 있으면 aria-label 이 " 선택" 처럼 뭉개져 빈 줄끼리 구분이 안 된다.
              // 그럴 때만 줄 번호로 대신 부른다.
              const rowLabel = r.name.trim() || `${i + 1}번째 줄`
              return (
                <tr key={r.id} className="border-t border-line align-top">
                  <td className="p-2">
                    <input
                      type="checkbox"
                      checked={r.checked}
                      aria-label={`${rowLabel} 선택`}
                      onChange={(e) => patch(r.id, { checked: e.target.checked })}
                    />
                  </td>
                  <td className="p-2">
                    <InlineEdit
                      value={r.name}
                      ariaLabel={`${rowLabel} 변수명`}
                      mono
                      placeholder="변수명을 입력하세요"
                      onCommit={(next) => patch(r.id, { name: next })}
                    />
                    {r.suggestedName && (
                      <button
                        type="button"
                        onClick={() => patch(r.id, { name: r.suggestedName!, suggestedName: null })}
                        className="mt-1 cursor-pointer rounded border border-border bg-none px-[6px] py-px text-[10.5px] text-faint-2 hover:text-fg-soft"
                      >
                        제안: {r.suggestedName} 적용
                      </button>
                    )}
                    {!r.name.trim() && (
                      <div className="mt-1 text-[10.5px] text-danger">이름이 없으면 저장할 수 없어요</div>
                    )}
                  </td>
                  <td className="p-2">
                    {/* 평문은 편집 중에만 보인다 - .env 는 한 파일에 시크릿이 여러 개다.
                        서비스를 못 알아본 값은 앞 4글자만 남긴다 - 접두어가 공개 정보라는
                        보장이 없어서다(백엔드 Stage1 의 keep_front=4 와 같은 기준). */}
                    <InlineEdit
                      value={r.value}
                      displayValue={mask(r.value, r.service ? 8 : 4)}
                      ariaLabel={`${rowLabel} 값`}
                      mono
                      onCommit={(next) => patch(r.id, { value: next })}
                    />
                  </td>
                  <td className="p-2 text-[11.5px] text-muted">
                    {r.typeLabel ? `${r.service} · ${r.typeLabel}` : '미상'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <span className="text-[11.5px] text-faint-2">
          {!project.trim() ? '컬렉션 이름을 입력해야 저장할 수 있어요' : `${checked}개 선택됨`}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={close}
            className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
          >
            취소
          </button>
          <button
            type="button"
            disabled={!canSave}
            onClick={save}
            className="cursor-pointer rounded-lg border-none bg-mint px-[14px] py-2 text-[12.5px] font-bold text-on-mint hover:brightness-[1.08] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? '저장 중...' : `${checked}개 저장`}
          </button>
        </div>
      </div>
    </Modal>
  )
}
