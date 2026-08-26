// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/** KeyLens 다크 UI 색상에 맞춘 최소 MUI 테마 — DataGrid 전용(전역 CssBaseline 미적용). */
import { createTheme } from '@mui/material/styles'

export const keylensMuiTheme = createTheme({
  palette: {
    mode: 'dark',
    background: {
      default: '#12151a', // --color-surface
      paper: '#12151a',
    },
    text: {
      primary: '#e7eaee', // --color-fg
      secondary: '#98a1ae', // --color-muted
    },
    divider: '#1b2027', // --color-line
    primary: {
      main: '#3ecf8e', // --color-mint
    },
  },
  typography: {
    fontFamily: 'inherit',
    fontSize: 12.5,
  },
  shape: {
    borderRadius: 10,
  },
})
