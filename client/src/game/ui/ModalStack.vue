<script setup lang="ts">
/**
 * This component is responsible for management of general modal windows
 * that require no immediate interaction.
 *
 * This component takes care of which modal is on top of which modal as well as
 * closing the top-most modal with the escape-key.
 *
 * Any Modal component that is used here, _should_ expose a close function
 * that can be get/set, as well as emit the following events:
 * - `focus`: when the modal is interacted with
 * - `close`: when the modal is closed
 */
import { computed, onMounted, onUnmounted, ref } from "vue";
import type { Component, ComputedRef } from "vue";

import { coreStore } from "../../store/core";
import type { NumberId } from "../id";
import { clientState } from "../systems/client/state";
import { gameState } from "../systems/game/state";

import DiceResults from "./dice/DiceResults.vue";
import Initiative from "./initiative/Initiative.vue";
import ClientSettings from "./settings/client/ClientSettings.vue";
import DmSettings from "./settings/dm/DmSettings.vue";
import FloorSettings from "./settings/FloorSettings.vue";
import LgSettings from "./settings/lg/LgSettings.vue";
import LocationSettings from "./settings/location/LocationSettings.vue";
import ShapeSettings from "./settings/shape/ShapeSettings.vue";

// Modal Conditions + Listing

const hasGameboard = coreStore.state.boardId !== undefined;
const hasGameboardClients = computed(() => clientState.reactive.clientBoards.size > 0);

const modals: (Component | { component: Component; condition: ComputedRef<boolean> })[] = [
    ClientSettings,
    { component: DmSettings, condition: gameState.isDmOrFake },
    { component: FloorSettings, condition: gameState.isDmOrFake },
    Initiative,
    { component: LgSettings, condition: computed(() => hasGameboardClients.value && gameState.isDmOrFake.value) },
    { component: LocationSettings, condition: gameState.isDmOrFake },
    ShapeSettings,
];
if (!hasGameboard) {
    modals.push(DiceResults);
}

// Core logic setup

type ModalIndex = NumberId<"modal">;

const refs: Record<ModalIndex, { close: () => void }> = {};

const modalOrder = ref<ModalIndex[]>(Array.from({ length: modals.length }, (_, i) => i as ModalIndex));
const openModals = new Set<ModalIndex>();

onMounted(() => window.addEventListener("keydown", checkEscape));
onUnmounted(() => window.removeEventListener("keydown", checkEscape));

const visibleModals = computed(() => {
    const _modals: { index: number; component: Component }[] = [];
    for (let i = 0; i < modalOrder.value.length; i++) {
        const modal = modals[modalOrder.value[i]];
        if (isComponent(modal)) {
            _modals.push({ index: i, component: modal });
        } else if (modal.condition.value) {
            _modals.push({ index: i, component: modal.component });
        }
    }
    return _modals;
});

// Type guards

function isComponent(x: Component | { component: Component }): x is Component {
    return !("component" in x);
}

function isReffable(x: Component): x is { close: () => void } {
    return "close" in x;
}

// Event handling

function focus(index: number): void {
    const idx = modalOrder.value.splice(index, 1)[0];
    modalOrder.value.push(idx);
    openModals.add(idx);
}

function close(index: number): void {
    openModals.delete(modalOrder.value[index]);
}

function checkEscape(event: KeyboardEvent): void {
    if (event.key === "Escape") {
        for (let i = modalOrder.value.length - 1; i >= 0; i--) {
            const index = modalOrder.value[i];
            if (openModals.has(index)) {
                refs[index].close();
                openModals.delete(index);
                break;
            }
        }
    }
}

function getComponentName(index: number): string {
    const modal = modals[index];
    const component = (isComponent(modal) ? modal : modal.component) as { __name: string };
    return component.__name;
}

function setModalRef(m: Component | null, index: number): void {
    if (m === null) return;
    if (isReffable(m)) refs[modalOrder.value[index]] = m;
    else console.warn(`Modal without exposed close function found. (${getComponentName(index)})`);
}
</script>

<template>
    <div>
        <component
            v-for="modal of visibleModals"
            :ref="(m: Component | null) => setModalRef(m, modal.index)"
            :is="modal.component"
            :key="modal.component"
            @focus="focus(modal.index)"
            @close="close(modal.index)"
            @update:visible="close(modal.index)"
        />
    </div>
</template>
