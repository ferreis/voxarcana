<script setup lang="ts">
import { ref } from 'vue'
import type { Project } from '../services/studio'
defineProps<{ projects: Project[]; projectId: string; disabled: boolean; create: (name: string) => Promise<void> }>()
defineEmits<{ select: [projectId: string] }>()
const creating = ref(false)
const projectName = ref('')
const saving = ref(false)
const error = ref('')
async function saveProject(create: (name: string) => Promise<void>) {
  if (!projectName.value.trim() || saving.value) return
  saving.value = true; error.value = ''
  try {
    await create(projectName.value.trim())
    creating.value = false; projectName.value = ''
  } catch (problem) {
    error.value = problem instanceof Error ? problem.message : 'Não consegui criar o projeto.'
  } finally { saving.value = false }
}
</script>

<template>
  <section class="project-selector" aria-label="Projeto atual">
    <div class="project-picker"><label class="sr-only" for="studio-project">Projeto</label><select id="studio-project" :value="projectId" :disabled="disabled || saving || !projects.length" @change="$emit('select', ($event.target as HTMLSelectElement).value)"><option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option></select></div>
    <button class="secondary-button" :disabled="disabled || saving || !projects.length" @click="creating = !creating">{{ creating ? 'Cancelar' : 'Novo projeto' }}</button>
    <form v-if="creating" class="project-create-form" @submit.prevent="saveProject(create)"><label class="sr-only" for="new-project-name">Nome do projeto</label><input id="new-project-name" v-model="projectName" maxlength="80" placeholder="Nome do projeto" required :disabled="disabled || saving"><button class="primary-button" :disabled="disabled || saving || !projectName.trim()">{{ saving ? 'Salvando…' : 'Criar projeto' }}</button></form>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.project-selector { position: relative; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; width: 100%; }
.project-picker { flex: 1; min-width: 0; }
.project-picker select { min-height: 38px; padding: 8px 10px; font-size: 11px; }
.project-selector > button { min-height: 38px; padding: 8px 10px; font-size: 11px; white-space: nowrap; }
.project-selector > p { flex-basis: 100%; margin: 0; }
.project-create-form { position: absolute; top: calc(100% + 12px); left: 0; z-index: 1; display: flex; gap: 8px; width: min(440px, calc(100vw - 32px)); padding: 16px; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-surface); box-shadow: 0 8px 24px #0005; }
form input { flex: 1; min-width: 0; }
@media (max-width: 767px) { form { flex-wrap: wrap; } }
</style>
