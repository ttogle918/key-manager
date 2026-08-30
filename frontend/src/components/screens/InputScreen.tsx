// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { DragEvent, ReactNode } from 'react'
import { TYPE_MAP } from '@/data/services'
import { useKeylens } from '@/store/keylensStore'
import { ManualEntryTab } from '@/components/input/ManualEntryTab'
import { ResultCard } from '@/components/input/ResultCard'
import { ResultsGrid } from '@/components/input/ResultsGrid'

/** 화면 1: 새 자격증명 분석 입력. */
export function InputScreen() {
  const s = useKeylens()
  const {
    vault,
    inputMode,
    analyzed,
    analyzing,
    ocrProgress,
    results,
    unknowns,
    apiError,
    attachedImage,
    attachedName,
    dragOver,
    urlVal,
    textVal,
    projVal,
    memoVal,
    sourceLabel,
  } = s

  const firstRun = vault.length === 0 && !analyzed && !analyzing
  const showStage = !analyzing && !analyzed
  const showResults = analyzed && results.length > 0
  const showUnknowns = analyzed && unknowns.length > 0
  const unknownsOnly = showUnknowns && results.length === 0
  const showDone = analyzed && results.length === 0 && unknowns.length === 0
  const hasRealImg = !!(attachedImage && attachedImage !== 'sample')
  const hasSampleImg = attachedImage === 'sample'
  const savableCount = results.filter((r) =>
    TYPE_MAP[r.service].some((t) => t.v === r.typeKey),
  ).length

  const onDragOver = (e: DragEvent) => {
    e.preventDefault()
    if (!dragOver) s.setDragOver(true)
  }
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    s.setDragOver(false)
    const f = e.dataTransfer?.files?.[0]
    if (f && f.type.startsWith('image')) {
      const rd = new FileReader()
      rd.onload = () => {
        if (typeof rd.result === 'string') s.attachImage(rd.result, f.name)
        else s.showToast('이미지를 읽지 못했어요 — 다른 파일로 시도해 주세요')
      }
      rd.onerror = () => s.showToast('이미지를 읽지 못했어요 — 다른 파일로 시도해 주세요')
      rd.readAsDataURL(f)
    } else if (f) {
      // .env 처럼 확장자가 없거나 text/plain 인 파일은 텍스트로 읽어 가져오기 모달을 연다.
      const rd = new FileReader()
      rd.onload = () => {
        if (typeof rd.result === 'string') s.openEnvImport(rd.result)
        else s.showToast('파일을 읽지 못했어요 - 다른 파일로 시도해 주세요')
      }
      rd.onerror = () => s.showToast('파일을 읽지 못했어요 - 다른 파일로 시도해 주세요')
      rd.readAsText(f)
    } else {
      s.attachSample()
    }
  }

  return (
    <div className="mx-auto max-w-[700px] px-8 pb-[90px] pt-[52px] [animation:klFadeUp_.35s_ease]">
      <h1 className="m-0 text-[20px] font-bold tracking-[-.015em]">새 자격증명 분석</h1>
      <p className="mb-6 mt-[7px] text-[13.5px] leading-[1.55] text-muted">
        스크린샷·URL·텍스트를 함께 던지면 맥락으로 정체를 판별해 공식 환경변수명에 매핑합니다.
        <br />
        모든 분석은 이 기기 안에서만 일어납니다.
        <br />
        <span className="text-dim-2">
          스크린샷은 라벨·URL로 &ldquo;어떤 키인지&rdquo; 판별하는 용도예요 — 값 자체가 화면에서
          마스킹(••••)돼 있으면 인식할 수 없으니, 실제 키 값은 꼭 아래 텍스트 붙여넣기에 넣어주세요.
        </span>
      </p>

      <div className="mb-5 flex gap-[6px]">
        <button
          type="button"
          onClick={() => s.setInputMode('auto')}
          className={
            'cursor-pointer rounded-[8px] border-none px-[14px] py-[8px] text-[12.5px] font-bold ' +
            (inputMode === 'auto' ? 'bg-[#191F26] text-fg' : 'bg-transparent text-muted')
          }
        >
          자동 분류
        </button>
        <button
          type="button"
          onClick={() => s.setInputMode('manual')}
          className={
            'cursor-pointer rounded-[8px] border-none px-[14px] py-[8px] text-[12.5px] font-bold ' +
            (inputMode === 'manual' ? 'bg-[#191F26] text-fg' : 'bg-transparent text-muted')
          }
        >
          직접 입력
        </button>
      </div>

      {inputMode === 'auto' && firstRun && (
        <div className="mb-5 flex items-center gap-[10px] rounded-[10px] border border-[rgba(62,207,142,.25)] bg-[rgba(62,207,142,.06)] px-[14px] py-3 text-[13px] text-mint-pale">
          <span className="size-[7px] flex-none rounded-full bg-mint" />
          처음이시네요 — 아래에 스크린샷을 던져보세요. 무엇인지 알아서 알아봅니다.
        </div>
      )}

      {inputMode === 'manual' && <ManualEntryTab />}

      {inputMode === 'auto' && showStage && (
        <div className="overflow-hidden rounded-[14px] border border-line-2 bg-surface-2">
          {/* 첨부 영역 */}
          <div className="px-[14px] pt-[14px]">
            {!attachedImage ? (
              <div
                onClick={s.attachSample}
                onDragOver={onDragOver}
                onDragLeave={() => s.setDragOver(false)}
                onDrop={onDrop}
                className="cursor-pointer rounded-[10px] border-[1.5px] border-dashed px-5 pb-[30px] pt-[34px] text-center transition-colors"
                style={{
                  borderColor: dragOver ? 'rgba(62,207,142,.7)' : '#2A313B',
                  background: dragOver ? 'rgba(62,207,142,.05)' : '#0E1116',
                }}
              >
                <div className="mx-auto flex size-10 items-center justify-center rounded-full border-[1.5px] border-border-strong bg-[#12151A]">
                  <div className="relative size-[10px] rounded-full border-2 border-mint">
                    <div className="absolute left-1/2 top-[9px] h-[7px] w-[3px] -translate-x-1/2 rounded-[1px] bg-mint" />
                  </div>
                </div>
                <div className="mt-3 text-[14px] font-semibold">
                  스크린샷이나 .env 파일을 여기로 던져보세요
                </div>
                <div className="mt-[5px] text-[12px] text-faint-2">
                  드래그 앤 드롭 · ⌘V 붙여넣기 · 클릭하면 샘플 첨부 · .env 는 변수 전체를 한 번에
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3 rounded-[10px] border border-[rgba(62,207,142,.3)] bg-[rgba(62,207,142,.04)] px-3 py-[10px]">
                {hasRealImg && (
                  <div
                    role="img"
                    aria-label="첨부 스크린샷"
                    className="size-[52px] w-[76px] flex-none rounded-[6px] border border-border bg-cover bg-center"
                    style={{ backgroundImage: `url(${attachedImage})` }}
                  />
                )}
                {hasSampleImg && (
                  <div className="flex h-[52px] w-[76px] flex-none items-center justify-center rounded-[6px] border border-border [background:repeating-linear-gradient(45deg,#12151A,#12151A_6px,#161B21_6px,#161B21_12px)]">
                    <span className="font-mono text-[9px] text-dim">sample</span>
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[12.5px] font-semibold">
                    {attachedName}
                  </div>
                  <div className="mt-[2px] text-[11px] text-mint-soft">
                    첨부됨 — 브라우저에서 OCR 후 분류에만 사용(이미지는 저장되지 않음)
                  </div>
                </div>
                <button
                  type="button"
                  onClick={s.removeImage}
                  className="flex-none cursor-pointer rounded-[6px] border border-border bg-none px-[10px] py-[5px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
                >
                  제거
                </button>
              </div>
            )}
          </div>

          {/* URL / 텍스트 / 컬렉션 / 메모 */}
          <div className="flex flex-col gap-3 px-[14px] pt-[14px]">
            <Field label="URL" hint="(선택)">
              <input
                value={urlVal}
                onChange={(e) => s.setUrl(e.target.value)}
                placeholder="https://www.notion.so/team/3f9a1c2e7b4d4e8a9c1f2d5e8a7b4c3f?v=…"
                className="w-full rounded-lg border border-border bg-surface px-3 py-[10px] font-mono text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
              />
            </Field>
            <Field
              label="텍스트 붙여넣기"
              hint="(실제 키 값은 꼭 여기에 — 스크린샷 속 값은 마스킹돼 있을 수 있어요)"
            >
              <textarea
                value={textVal}
                onChange={(e) => s.setText(e.target.value)}
                rows={3}
                placeholder={'NOTION_KEY=secret_ntn_…\nkakao rest: 4f8e2a1b… — 아무 형식이나 붙여넣으세요'}
                className="w-full resize-y rounded-lg border border-border bg-surface px-3 py-[10px] font-mono text-[12px] leading-[1.6] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
              />
            </Field>
            <div className="flex gap-3">
              <div className="w-[200px] flex-none">
                <Field label="컬렉션" hint="(선택)">
                  <input
                    value={projVal}
                    onChange={(e) => s.setProj(e.target.value)}
                    list="kl-projects"
                    placeholder="예: 개인 블로그"
                    className="w-full rounded-lg border border-border bg-surface px-3 py-[10px] text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
                  />
                </Field>
              </div>
              <div className="min-w-0 flex-1">
                <Field label="메모" hint="(언제·왜 발급받은 키인가요?)">
                  <input
                    value={memoVal}
                    onChange={(e) => s.setMemo(e.target.value)}
                    placeholder="예: 6월 사이드프로젝트 블로그 자동화용으로 발급"
                    className="w-full rounded-lg border border-border bg-surface px-3 py-[10px] text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
                  />
                </Field>
              </div>
            </div>
          </div>

          <div className="mt-[2px] flex items-center gap-3 p-[14px]">
            <div className="flex-1 text-[11.5px] text-dim-2">
              아무것도 넣지 않고 분석하면 샘플 스크린샷으로 시연합니다.
            </div>
            <button
              type="button"
              onClick={s.startAnalyze}
              className="flex-none cursor-pointer rounded-[9px] border-none bg-mint px-[22px] py-[11px] text-[13.5px] font-bold text-on-mint hover:brightness-[1.08]"
            >
              분석
            </button>
          </div>
        </div>
      )}

      {analyzing && (
        <div className="relative overflow-hidden rounded-[14px] border border-border bg-surface px-6 py-[60px] text-center [animation:klFade_.2s]">
          <div className="absolute inset-x-[6%] top-[10%] h-[2px] rounded-[2px] bg-[linear-gradient(90deg,transparent,rgba(62,207,142,.7),transparent)] [animation:klScan_1.5s_ease-in-out_infinite]" />
          <div className="mx-auto size-[34px] rounded-full border-2 border-border border-t-mint [animation:klRingSpin_.8s_linear_infinite]" />
          <div className="mt-[18px] text-[14.5px] font-semibold">
            {ocrProgress !== null ? '스크린샷 인식 중…' : '분류 중…'}
          </div>
          <div className="mt-[6px] font-mono text-[12.5px] text-faint-2">
            {ocrProgress !== null
              ? `브라우저에서 OCR — ${Math.round(ocrProgress * 100)}% (기기 밖으로 나가지 않음)`
              : '형식 시그니처 · 주변 텍스트 · URL 구조 대조'}
          </div>
        </div>
      )}

      {analyzed && apiError && (
        <div className="mb-3 flex items-center gap-[10px] rounded-[10px] border border-[rgba(227,179,65,.28)] bg-[rgba(227,179,65,.05)] px-[14px] py-3 text-[12.5px] text-amber-soft [animation:klFade_.2s]">
          <span className="inline-block size-[7px] flex-none rotate-45 bg-amber" />
          {apiError} — 아래는 샘플 목업입니다. 서버가 켜져 있으면 실제 분류로 동작해요.
        </div>
      )}

      {showResults && (
        <div className="[animation:klFadeUp_.3s_ease]">
          <div className="mb-[14px] flex items-center gap-[10px]">
            <div className="flex-1 text-[14px]">
              <strong className="font-bold">{results.length}개 항목 발견</strong>{' '}
              <span className="text-[12.5px] text-faint-2">· {sourceLabel}</span>
            </div>
            <button
              type="button"
              onClick={s.resetResults}
              className="cursor-pointer rounded-lg border border-border bg-none px-3 py-[7px] text-[12px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
            >
              새로 분석
            </button>
            <button
              type="button"
              onClick={s.saveAll}
              className="cursor-pointer rounded-lg border border-[rgba(62,207,142,.35)] bg-[#1B2620] px-3 py-[7px] text-[12px] font-bold text-mint-soft hover:bg-[#1F2E26]"
            >
              {savableCount}개 모두 저장
            </button>
            {s.explainAvailable && hasRealImg && (
              <button
                type="button"
                onClick={s.openExplain}
                title="화면 각 영역이 뭘 의미하는지 박스로 설명(로컬 LLM 필요)"
                className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[7px] text-[12px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
              >
                이 화면 설명해줘
              </button>
            )}
          </div>
          <ResultsGrid results={results} />
          {results.map((r) => (
            <ResultCard key={r.id} r={r} />
          ))}
        </div>
      )}

      {showUnknowns && (
        <div className="mt-3 rounded-[12px] border border-[rgba(227,179,65,.28)] bg-[rgba(227,179,65,.04)] p-[14px] [animation:klFadeUp_.3s_ease]">
          <div className="flex items-center gap-[10px]">
            <div className="flex flex-1 items-center gap-2 text-[13px] font-bold text-amber">
              <span className="inline-block size-[7px] flex-none rotate-45 bg-amber" />값만으로 판별 불가 — {unknowns.length}건
            </div>
            {unknownsOnly && (
              <button
                type="button"
                onClick={s.resetResults}
                className="flex-none cursor-pointer rounded-lg border border-border bg-none px-3 py-[7px] text-[12px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
              >
                새로 분석
              </button>
            )}
          </div>
          <div className="mb-[10px] mt-[5px] text-[12px] leading-[1.5] text-muted">
            형식이 같은 종류가 여럿이라 값만으론 못 가립니다. 맥락 기반 분류(Stage2)에서 라벨·URL로 구분할 예정이에요.
          </div>
          {unknowns.map((u, i) => (
            <div
              key={`${u.keyName}-${i}`}
              className="mt-[6px] flex items-center gap-[10px] rounded-[8px] border border-line bg-inset px-3 py-[8px]"
            >
              <span className="flex-none font-mono text-[11px] text-faint">{u.keyName}</span>
              <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[12px] text-fg-soft">
                {u.masked}
              </span>
              <span className="flex-none font-mono text-[10.5px] text-dim-2">{u.format}</span>
            </div>
          ))}
        </div>
      )}

      {showDone && (
        <div className="rounded-[14px] border border-[rgba(62,207,142,.25)] bg-[rgba(62,207,142,.04)] px-6 py-12 text-center [animation:klFadeUp_.3s_ease]">
          <div className="mx-auto flex size-11 items-center justify-center rounded-full border border-[rgba(62,207,142,.4)] bg-[rgba(62,207,142,.12)] text-[19px] font-extrabold text-mint">
            ✓
          </div>
          <div className="mt-4 text-[15px] font-bold">모두 저장했어요</div>
          <div className="mt-[5px] text-[12.5px] text-muted">
            값은 AES-256-GCM으로 암호화되어 이 기기에만 보관됩니다.
          </div>
          <div className="mt-5 flex justify-center gap-2">
            <button
              type="button"
              onClick={s.goVault}
              className="cursor-pointer rounded-lg border-none bg-mint px-4 py-[9px] text-[12.5px] font-bold text-on-mint hover:brightness-[1.08]"
            >
              보관함 보기
            </button>
            <button
              type="button"
              onClick={s.resetResults}
              className="cursor-pointer rounded-lg border border-border bg-none px-4 py-[9px] text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
            >
              새로 분석
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint: string
  children: ReactNode
}) {
  return (
    <div>
      <div className="mb-[6px] text-[11.5px] font-semibold text-muted-2">
        {label} <span className="font-medium text-dim-2">{hint}</span>
      </div>
      {children}
    </div>
  )
}
