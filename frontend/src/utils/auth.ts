export function getRole(): string | null {
  return (
    document.cookie
      .split('; ')
      .find((r) => r.startsWith('role='))
      ?.split('=')[1] ?? null
  )
}
