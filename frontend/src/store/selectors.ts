// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useKeylens } from '@/store/keylensStore'

/** 보관함 + 현재 입력 중인 프로젝트명을 합쳐 정렬한 고유 목록. */
export function useProjectNames(): string[] {
  const vault = useKeylens((s) => s.vault)
  const projVal = useKeylens((s) => s.projVal)
  const set: string[] = []
  vault.forEach((v) => {
    if (v.project && !set.includes(v.project)) set.push(v.project)
  })
  if (projVal.trim() && !set.includes(projVal.trim())) set.push(projVal.trim())
  set.sort()
  return set
}
