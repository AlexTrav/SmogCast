// эпизод смога для «машины времени»: окно из days суток с наибольшим средним PM2.5 (по суточным средним);
// возвращает индексы первого и последнего дня окна
export function worstWindow(means: (number | null)[], days = 7): { from: number; to: number; mean: number } | null {
  let best: { from: number; to: number; mean: number } | null = null
  for (let i = 0; i + days <= means.length; i++) {
    const window = means.slice(i, i + days)
    if (window.some((v) => v == null)) continue
    const mean = (window as number[]).reduce((a, b) => a + b, 0) / days
    if (!best || mean > best.mean) best = { from: i, to: i + days - 1, mean }
  }
  return best
}

// индекс часа в почасовом ряду для момента t (ряд идёт подряд с шагом 1 ч от start)
export function hourIndex(start: string, t: Date | string): number {
  return Math.round((new Date(t).getTime() - new Date(start).getTime()) / 3_600_000)
}
