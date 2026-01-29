<template>
  <el-button
    circle
    class="action-btn"
    :title="title"
    :disabled="disabled"
    @click="onClick"
  >
    {{ label }}
  </el-button>
</template>

<script setup lang="ts">

const props = defineProps<{
  label: string
  title: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'click'): void
}>()

const onClick = () => {
  if (props.disabled) return
  emit('click')
}
</script>

<style scoped>
.action-btn {
  width: 44px;
  height: 44px;
  font-size: 14px;
  font-weight: bold;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.4);
  transform: scale(1.05);
}
</style>
