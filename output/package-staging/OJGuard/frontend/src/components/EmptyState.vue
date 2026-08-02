<script setup lang="ts">
withDefaults(defineProps<{ title: string; description?: string }>(), { description: '' })
</script>

<template>
  <div class="empty-state"><span>◇</span><strong>{{ title }}</strong><p>{{ description }}</p></div>
</template>
