<template>
  <div
    ref="padRef"
    class="joystick"
    :style="{ width: `${size}px`, height: `${size}px` }"
    @pointerdown="onPointerDown"
  >
    <div
      class="joystick__stick"
      :style="{
        width: `${stickSize}px`,
        height: `${stickSize}px`,
        transform: `translate(calc(-50% + ${offset.x}px), calc(-50% + ${offset.y}px))`
      }"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';

type JoystickPayload = { x: number; y: number }

const emit = defineEmits<{
  (e: 'change', payload: JoystickPayload): void
  (e: 'end'): void
}>()

const props = withDefaults(
  defineProps<{
    size?: number
    stickSize?: number
  }>(),
  {
    size: 140,
    stickSize: 60,
  }
)

const padRef = ref<HTMLDivElement | null>(null)
const offset = ref({ x: 0, y: 0 })
const isActive = ref(false)

const radius = computed(() => props.size / 2)

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const updateFromPointer = (event: PointerEvent) => {
  if (!padRef.value) return
  const rect = padRef.value.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2
  const dx = event.clientX - centerX
  const dy = event.clientY - centerY
  const r = radius.value

  const distance = Math.hypot(dx, dy)
  const scale = distance > r ? r / distance : 1
  const x = clamp(dx * scale, -r, r)
  const y = clamp(dy * scale, -r, r)

  offset.value = { x, y }
  // 坐标约定：上为 +x，左为 +y；归一化到 [-1, 1]
  const nx = r === 0 ? 0 : (-y / r)
  const ny = r === 0 ? 0 : (-x / r)
  emit('change', { x: nx, y: ny })
}

const onPointerMove = (event: PointerEvent) => {
  if (!isActive.value) return
  updateFromPointer(event)
}

const onPointerUp = (event?: PointerEvent) => {
  if (!isActive.value) return
  isActive.value = false
  offset.value = { x: 0, y: 0 }
  emit('end')
  if (event?.pointerId != null) {
    padRef.value?.releasePointerCapture(event.pointerId)
  }
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
}

const onPointerDown = (event: PointerEvent) => {
  event.preventDefault()
  event.stopPropagation()
  isActive.value = true
  padRef.value?.setPointerCapture(event.pointerId)
  updateFromPointer(event)
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
}

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
})
</script>

<style scoped>
.joystick {
  position: relative;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: none;
  pointer-events: auto;
}

.joystick__stick {
  position: absolute;
  left: 50%;
  top: 50%;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.5);
  transform: translate(0, 0);
  transition: transform 80ms ease;
}
</style>
