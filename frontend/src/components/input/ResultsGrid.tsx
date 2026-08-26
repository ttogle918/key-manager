// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 분석 결과 요약 표(MUI DataGrid, Community/MIT) — 환경변수 : 값 형태로 한눈에 보여준다.
 * 실제 저장·종류 선택·메모 편집 같은 상호작용은 그대로 아래 ResultCard 가 담당한다(이 표는 요약 전용).
 */
import { ThemeProvider } from '@mui/material/styles'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import { CONF_META, SVC_META, TYPE_MAP } from '@/data/services'
import { keylensMuiTheme } from '@/mui/theme'
import type { AnalysisResult } from '@/types'

interface Row {
  id: string
  service: string
  envName: string
  kindLabel: string
  masked: string
  confLabel: string
  confKey: keyof typeof CONF_META
}

function toRow(r: AnalysisResult): Row {
  const tmap = TYPE_MAP[r.service]
  const cur = tmap.find((t) => t.v === r.typeKey) || null
  const confKey = r.conflict ? (cur ? 'manual' : 'low') : r.conf
  return {
    id: r.id,
    service: r.service,
    envName: cur ? cur.var : '(종류 미확정)',
    kindLabel: cur ? cur.label : '확인 필요',
    masked: r.masked,
    confLabel: CONF_META[confKey].label,
    confKey,
  }
}

const columns: GridColDef<Row>[] = [
  {
    field: 'service',
    headerName: '서비스',
    width: 110,
    renderCell: (params) => {
      const svc = SVC_META[params.value as string]
      return (
        <span className="flex items-center gap-[7px]">
          {svc && (
            <span
              className="flex size-5 flex-none items-center justify-center rounded-[5px] text-[10px] font-extrabold"
              style={{ background: svc.bg, color: svc.fg }}
            >
              {svc.tile}
            </span>
          )}
          <span className="text-[12.5px]">{params.value}</span>
        </span>
      )
    },
  },
  { field: 'envName', headerName: '환경변수', flex: 1, minWidth: 200, cellClassName: 'font-mono' },
  { field: 'kindLabel', headerName: '종류', width: 130 },
  { field: 'masked', headerName: '값(마스킹)', flex: 1, minWidth: 200, cellClassName: 'font-mono' },
  {
    field: 'confLabel',
    headerName: '신뢰도',
    width: 120,
    renderCell: (params) => {
      const row = params.row as Row
      const cm = CONF_META[row.confKey]
      return (
        <span
          className="whitespace-nowrap rounded-[6px] border px-2 py-[3px] text-[11px] font-bold"
          style={{ background: cm.bg, color: cm.fg, borderColor: cm.border }}
        >
          {params.value}
        </span>
      )
    },
  },
]

/** 분석 결과 목록을 요약 표로. 항목이 없으면 아무것도 렌더링하지 않는다. */
export function ResultsGrid({ results }: { results: AnalysisResult[] }) {
  if (!results.length) return null
  const rows = results.map(toRow)

  return (
    <ThemeProvider theme={keylensMuiTheme}>
      <div className="mb-4 overflow-hidden rounded-[11px] border border-line-2">
        <DataGrid
          rows={rows}
          columns={columns}
          density="compact"
          hideFooter={rows.length <= 10}
          disableRowSelectionOnClick
          sx={{
            border: 'none',
            fontFamily: 'inherit',
            fontSize: '12.5px',
            '& .MuiDataGrid-columnHeaders': { borderBottom: '1px solid #1b2027' },
            '& .MuiDataGrid-cell': { borderBottom: '1px solid #1b2027' },
            '& .MuiDataGrid-cell:focus, & .MuiDataGrid-cell:focus-within': { outline: 'none' },
            '& .MuiDataGrid-columnHeader:focus, & .MuiDataGrid-columnHeader:focus-within': {
              outline: 'none',
            },
          }}
        />
      </div>
    </ThemeProvider>
  )
}
