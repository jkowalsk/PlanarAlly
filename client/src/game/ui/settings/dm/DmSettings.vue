<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import PanelModal from "../../../../core/components/modals/PanelModal.vue";
import { uiSystem } from "../../../systems/ui";
import { uiState } from "../../../systems/ui/state";
import FloorSettings from "../location/FloorSettings.vue";
import GridSettings from "../location/GridSettings.vue";
import VariaSettings from "../location/VariaSettings.vue";
import VisionSettings from "../location/VisionSettings.vue";

import AdminSettings from "./AdminSettings.vue";
import { DmSettingCategory } from "./categories";

const { t } = useI18n();

const visible = computed({
    get() {
        return uiState.reactive.showDmSettings;
    },
    set(visible: boolean) {
        uiSystem.showDmSettings(visible);
    },
});

function close(): void {
    visible.value = false;
}
defineExpose({ close });

const categoryNames = computed(() => {
    return [
        DmSettingCategory.Admin,
        DmSettingCategory.Grid,
        DmSettingCategory.Vision,
        DmSettingCategory.Floor,
        DmSettingCategory.Varia,
    ];
});
</script>

<template>
    <PanelModal v-model:visible="visible" :categories="categoryNames" :applyTranslation="true">
        <template v-slot:title>{{ t("game.ui.settings.dm.DmSettings.dm_settings") }}</template>
        <template v-slot:default="{ selection }">
            <AdminSettings v-show="selection === DmSettingCategory.Admin" />
            <GridSettings v-show="selection === DmSettingCategory.Grid" />
            <VisionSettings v-show="selection === DmSettingCategory.Vision" />
            <FloorSettings v-show="selection === DmSettingCategory.Floor" />
            <VariaSettings v-show="selection === DmSettingCategory.Varia" />
        </template>
    </PanelModal>
</template>
