import { g2l } from "../../../core/conversions";
import type { GlobalPoint } from "../../../core/geometry";
import { FOG_COLOUR } from "../../colour";
import type { GlobalId, LocalId } from "../../id";
import type { IShape } from "../../interfaces/shape";
import type { ServerRect } from "../../models/shapes";
import { positionState } from "../../systems/position/state";
import { getProperties } from "../../systems/properties/state";
import type { ShapeProperties } from "../../systems/properties/state";
import type { SHAPE_TYPE } from "../types";

import { BaseRect } from "./baseRect";

export class Rect extends BaseRect implements IShape {
    type: SHAPE_TYPE = "rect";

    constructor(
        topleft: GlobalPoint,
        w: number,
        h: number,
        options?: {
            id?: LocalId;
            uuid?: GlobalId;
            isSnappable?: boolean;
        },
        properties?: Partial<ShapeProperties>,
    ) {
        super(topleft, w, h, options, properties);
    }

    get isClosed(): boolean {
        return true;
    }

    asDict(): ServerRect {
        return super.getBaseDict();
    }

    draw(ctx: CanvasRenderingContext2D): void {
        super.draw(ctx);
        const props = getProperties(this.id)!;
        if (props.fillColour === "fog") ctx.fillStyle = FOG_COLOUR;
        else ctx.fillStyle = props.fillColour;
        const loc = g2l(this.refPoint);
        const center = g2l(this.center);
        const state = positionState.readonly;
        ctx.fillRect(loc.x - center.x, loc.y - center.y, this.w * state.zoom, this.h * state.zoom);
        if (props.strokeColour[0] !== "rgba(0, 0, 0, 0)") {
            ctx.strokeStyle = props.strokeColour[0];
            ctx.lineWidth = this.strokeWidth;
            ctx.strokeRect(loc.x - center.x, loc.y - center.y, this.w * state.zoom, this.h * state.zoom);
        }

        super.drawPost(ctx);
    }
}
