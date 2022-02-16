import { uuidv4 } from "../../../core/utils";
import type { LocalId } from "../../id";

import type { Tracker, UiTracker } from "./models";

export function createEmptyUiTracker(shape: LocalId): UiTracker {
    return {
        shape,
        temporary: true,
        ...createEmptyTracker(),
        name: "New tracker",
    };
}

export function createEmptyTracker(): Tracker {
    return {
        uuid: uuidv4(),
        name: "",
        value: 0,
        maxvalue: 0,
        visible: false,
        draw: false,
        primaryColor: "#00FF00",
        secondaryColor: "#888888",
    };
}
