import { describe, expect, it } from 'vitest'
import { TIPS } from '../utils/advice'
import { MODEL_ORDER, modelTerm } from '../utils/models'
import en from './en'
import kk from './kk'
import ru from './ru'

// переводы: на всех трёх языках одинаковые ключи, а у каждой подсказки «?» на сайте есть название и текст

type Tree = { [key: string]: string | Tree }

function keys(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([k, v]) => (typeof v === 'string' ? [prefix + k] : keys(v, `${prefix}${k}.`)))
}

// ключи подсказок прямо из исходников: term="…" и подсказки ко всем вариантам вычисляемых ключей
const sources = import.meta.glob('../**/*.vue', { query: '?raw', import: 'default', eager: true }) as Record<string, string>
const used = new Set<string>()
for (const text of Object.values(sources)) for (const m of text.matchAll(/\bterm="([a-zA-Z_]+)"/g)) used.add(m[1])
for (const tip of TIPS) used.add(`tip_${tip}`)
for (const model of [...MODEL_ORDER, 'persistence', 'cams', 'a+b']) used.add(modelTerm(model))
// подсказки, ключ которых задан в данных компонента (плитки, «Над городом», «Почему такой прогноз»)
for (const text of Object.values(sources)) for (const m of text.matchAll(/\bterm: '([a-zA-Z_]+)'/g)) used.add(m[1])

describe('переводы', () => {
  it('казахский и английский – те же ключи, что русский', () => {
    const base = keys(ru as Tree).sort()
    expect(keys(kk as Tree).sort()).toEqual(base)
    expect(keys(en as Tree).sort()).toEqual(base)
  })

  it('у каждой подсказки «?» есть название и объяснение на всех языках', () => {
    expect(used.size).toBeGreaterThan(60)
    for (const [lang, tree] of Object.entries({ ru, kk, en })) {
      const terms = (tree as Tree).terms as Record<string, string>
      for (const term of used) {
        expect(terms[`${term}Name`], `${lang}: terms.${term}Name`).toBeTruthy()
        expect(terms[term]?.length ?? 0, `${lang}: terms.${term}`).toBeGreaterThan(40)
      }
    }
  })

  it('в текстах нет длинного тире', () => {
    for (const tree of [ru, kk, en]) expect(JSON.stringify(tree)).not.toContain('—')
  })
})
