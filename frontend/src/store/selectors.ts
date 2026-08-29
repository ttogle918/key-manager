// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useKeylens } from '@/store/keylensStore'
import { projectKey } from '@/lib/format'

/** 보관함 + 현재 입력 중인 컬렉션명을 합쳐 정렬한 고유 목록. */
export function useProjectNames(): string[] {
  const vault = useKeylens((s) => s.vault)
  const projVal = useKeylens((s) => s.projVal)
  const set: string[] = []
  vault.forEach((v) => {
    const k = projectKey(v)
    if (!set.includes(k)) set.push(k)
  })
  if (projVal.trim() && !set.includes(projVal.trim())) set.push(projVal.trim())
  set.sort()
  return set
}
