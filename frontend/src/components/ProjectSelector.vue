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
    <div class="project-picker"><label for="studio-project">Projeto</label><select id="studio-project" :value="projectId" :disabled="disabled || saving || !projects.length" @change="$emit('select', ($event.target as HTMLSelectElement).value)"><option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option></select></div>
    <button class="secondary-button" :disabled="disabled || saving || !projects.length" @click="creating = !creating">{{ creating ? 'Cancelar' : 'Novo projeto' }}</button>
    <form v-if="creating" @submit.prevent="saveProject(create)"><label class="sr-only" for="new-project-name">Nome do projeto</label><input id="new-project-name" v-model="projectName" maxlength="80" placeholder="Nome do projeto" required :disabled="disabled || saving"><button class="primary-button" :disabled="disabled || saving || !projectName.trim()">{{ saving ? 'Salvando…' : 'Criar projeto' }}</button></form>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.project-selector { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; margin-bottom: 24px; }
.project-picker { flex: 1; min-width: 180px; max-width: 420px; }
.project-selector > button { min-height: 42px; }
.project-selector > p { flex-basis: 100%; margin: 0; }
form { display: flex; gap: 12px; flex-basis: 100%; max-width: 620px; }
form input { flex: 1; min-width: 0; }
@media (max-width: 767px) { form { flex-wrap: wrap; } }
</style>
