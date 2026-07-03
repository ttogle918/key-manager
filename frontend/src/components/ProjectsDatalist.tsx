// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useProjectNames } from '@/store/selectors'

/** 프로젝트 입력칸들이 공유하는 자동완성 목록(id="kl-projects"). */
export function ProjectsDatalist() {
  const names = useProjectNames()
  return (
    <datalist id="kl-projects">
      {names.map((name) => (
        <option key={name} value={name} />
      ))}
    </datalist>
  )
}
