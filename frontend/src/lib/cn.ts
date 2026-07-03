// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Tailwind 클래스 병합 유틸(충돌 시 뒤쪽 우선). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
