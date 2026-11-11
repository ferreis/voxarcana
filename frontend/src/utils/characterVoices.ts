import type { SavedCharacter } from '../services/studio'

export function characterIdentity(name: string): string {
  return name.normalize('NFKD').toLocaleLowerCase('pt-BR').replace(/\p{M}/gu, '').replace(/[^\p{L}\p{N}]/gu, '')
}

export function findSavedCharacter(characters: SavedCharacter[], name: string): SavedCharacter | undefined {
  const identity = characterIdentity(name)
  const namedCharacter = characters.find(character => characterIdentity(character.name) === identity)
  if (namedCharacter) return namedCharacter
  const aliasMatches = characters.filter(character => character.aliases.some(alias => characterIdentity(alias) === identity))
  return aliasMatches.length === 1 ? aliasMatches[0] : undefined
}

export function voiceUsedByAnother(characters: SavedCharacter[], voiceId: string, characterId?: string): boolean {
  return characters.some(character => character.id !== characterId && character.voice_id === voiceId)
}
