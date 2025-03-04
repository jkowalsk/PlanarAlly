# ruff: noqa
"""
This file is responsible for migrating old save files to new versions.

The `SAVE_VERSION` listed below lists the active save file format.

IMPORTANT:
When writing migrations make sure that these things are respected:
- Prefer raw sql over orm methods as these can lead to issues when you're multiple versions behind.
- Some column names clash with some sql keywords (e.g. 'index', 'group'), make sure that these are handled correctly
    - i.e. surround them at all times with quotes.
    - WHEN USING THIS IN A SELECT STATEMENT MAKE SURE YOU USE " AND NOT ' OR YOU WILL HAVE A STRING LITERAL
- When changing models that have inherited parents or children also update those with queries
    - e.g. a column added to Circle also needs to be added to CircularToken
"""

SAVE_VERSION = 85

import json
import logging
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any, List, Optional

from playhouse.sqlite_ext import SqliteExtDatabase

from .config import SAVE_FILE
from .models import ALL_MODELS, Constants
from .models.db import db as ACTIVE_DB
from .utils import FILE_DIR, OldVersionException, UnknownVersionException

logger: logging.Logger = logging.getLogger("PlanarAllyServer")
logger.setLevel(logging.INFO)


def get_save_version(db: SqliteExtDatabase):
    return db.execute_sql("SELECT save_version FROM constants").fetchone()[0]


def inc_save_version(db: SqliteExtDatabase):
    db.execute_sql("UPDATE constants SET save_version = save_version + 1")


def create_new_db(db: SqliteExtDatabase, version: int):
    db.create_tables(ALL_MODELS)
    Constants.create(
        save_version=version,
        secret_token=secrets.token_bytes(32),
        api_token=secrets.token_hex(32),
    )


def check_existence() -> bool:
    if not SAVE_FILE.exists():
        logger.warning("Provided save file does not exist.  Creating a new one.")
        create_new_db(ACTIVE_DB, SAVE_VERSION)
        return True
    return False


def upgrade(db: SqliteExtDatabase, version: int):
    if version < 64:
        raise OldVersionException(
            f"Upgrade code for this version is >1 year old and is no longer in the active codebase to reduce clutter. You can still find this code on github, contact me for more info."
        )

    db.foreign_keys = False

    if version == 64:
        # Add LocationOptions.map_background_{air/ground/underground}
        # Add Floor.type_ and Floor.background_color
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE location_options ADD COLUMN air_map_background TEXT DEFAULT NULL"
            )
            db.execute_sql(
                "ALTER TABLE location_options ADD COLUMN ground_map_background TEXT DEFAULT NULL"
            )
            db.execute_sql(
                "ALTER TABLE location_options ADD COLUMN underground_map_background TEXT DEFAULT NULL"
            )
            db.execute_sql("SELECT default_options_id FROM room")

            db.execute_sql(
                "ALTER TABLE floor ADD COLUMN type_ INTEGER NOT NULL DEFAULT 1"
            )
            db.execute_sql(
                "ALTER TABLE floor ADD COLUMN background_color TEXT DEFAULT NULL"
            )
    elif version == 65:
        # Migrate new saves to allow NULL for map backgrounds
        with db.atomic():
            db.execute_sql(
                "CREATE TEMPORARY TABLE _location_options_65 AS SELECT * FROM location_options"
            )
            db.execute_sql("DROP TABLE location_options")
            db.execute_sql(
                'CREATE TABLE IF NOT EXISTS "location_options" ("id" INTEGER NOT NULL PRIMARY KEY, "unit_size" REAL, "unit_size_unit" TEXT, "use_grid" INTEGER, "full_fow" INTEGER, "fow_opacity" REAL, "fow_los" INTEGER, "vision_mode" TEXT, "vision_min_range" REAL, "vision_max_range" REAL, "spawn_locations" TEXT NOT NULL, "move_player_on_token_change" INTEGER, "grid_type" TEXT, "air_map_background" TEXT, "ground_map_background" TEXT, "underground_map_background" TEXT);'
            )
            db.execute_sql(
                'INSERT INTO "location_options" (id, unit_size, unit_size_unit, use_grid, full_fow, fow_opacity, fow_los, vision_mode, vision_min_range, vision_max_range, spawn_locations, move_player_on_token_change, grid_type, air_map_background, ground_map_background, underground_map_background) SELECT id, unit_size, unit_size_unit, use_grid, full_fow, fow_opacity, fow_los, vision_mode, vision_min_range, vision_max_range, spawn_locations, move_player_on_token_change, grid_type, air_map_background, ground_map_background, underground_map_background FROM _location_options_65 '
            )
    elif version == 66:
        # Add Shape.IsDoor
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE shape ADD COLUMN is_door INTEGER DEFAULT 0 NOT NULL"
            )
    elif version == 67:
        # Add Shape.IsTeleportZone
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE shape ADD COLUMN is_teleport_zone INTEGER DEFAULT 0 NOT NULL"
            )
    elif version == 68:
        # Model change in logic options (doorConditions -> door, conditions -> permissions)
        with db.atomic():
            data = db.execute_sql("SELECT uuid, options FROM shape")
            for row in data.fetchall():
                uuid, options = row
                if options is None:
                    continue

                unpacked_options = json.loads(options)
                changed = False

                for option in unpacked_options:
                    if option[0] == "doorConditions":
                        option[0] = "door"
                        changed = True
                    elif option[0] == "teleport":
                        option[1]["permissions"] = option[1]["conditions"]
                        del option[1]["conditions"]
                        changed = True

                if changed:
                    db.execute_sql(
                        "UPDATE shape SET options=? WHERE uuid=?",
                        (json.dumps(unpacked_options), uuid),
                    )
    elif version == 69:
        # Change Room.logo on_delete logic from cascade to set null
        with db.atomic():
            db.execute_sql("CREATE TEMPORARY TABLE _room_69 AS SELECT * FROM room")
            db.execute_sql("DROP TABLE room")
            db.execute_sql(
                'CREATE TABLE IF NOT EXISTS "room" ("id" INTEGER NOT NULL PRIMARY KEY, "name" TEXT NOT NULL, "creator_id" INTEGER NOT NULL, "invitation_code" TEXT NOT NULL, "is_locked" INTEGER NOT NULL, "default_options_id" INTEGER NOT NULL, "logo_id" INTEGER, FOREIGN KEY ("creator_id") REFERENCES "user" ("id") ON DELETE CASCADE, FOREIGN KEY ("default_options_id") REFERENCES "location_options" ("id") ON DELETE CASCADE, FOREIGN KEY ("logo_id") REFERENCES "asset" ("id") ON DELETE SET NULL);'
            )
            db.execute_sql(
                'INSERT INTO "room" (id, name, creator_id, invitation_code, is_locked, default_options_id, logo_id) SELECT id, name, creator_id, invitation_code, is_locked, default_options_id, logo_id FROM _room_69'
            )
    elif version == 70:
        # Move door logic permissions to door logic options block
        with db.atomic():
            data = db.execute_sql("SELECT uuid, options FROM shape")
            for row in data.fetchall():
                uuid, options = row
                if options is None:
                    continue

                unpacked_options = json.loads(options)
                changed = False

                for option in unpacked_options:
                    if option[0] == "door" and "toggleMode" not in option[1]:
                        option[1] = {"permissions": option[1], "toggleMode": "both"}
                        changed = True

                if changed:
                    db.execute_sql(
                        "UPDATE shape SET options=? WHERE uuid=?",
                        (json.dumps(unpacked_options), uuid),
                    )
    elif version == 71:
        # Add User.colour_history
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE user ADD COLUMN colour_history TEXT DEFAULT NULL"
            )
    elif version == 72:
        # Change default zoom level from 1.0 to 0.2
        with db.atomic():
            db.execute_sql(
                "CREATE TEMPORARY TABLE _location_user_option_72 AS SELECT * FROM location_user_option"
            )
            db.execute_sql("DROP TABLE location_user_option")
            db.execute_sql(
                'CREATE TABLE IF NOT EXISTS "location_user_option" ("id" INTEGER NOT NULL PRIMARY KEY, "location_id" INTEGER NOT NULL, "user_id" INTEGER NOT NULL, "pan_x" REAL DEFAULT 0 NOT NULL, "pan_y" REAL DEFAULT 0 NOT NULL, "zoom_display" REAL DEFAULT 0.2 NOT NULL, "active_layer_id" INTEGER, FOREIGN KEY ("location_id") REFERENCES "location" ("id") ON DELETE CASCADE, FOREIGN KEY ("user_id") REFERENCES "user" ("id") ON DELETE CASCADE, FOREIGN KEY ("active_layer_id") REFERENCES "layer" ("id"));'
            )
            db.execute_sql(
                'INSERT INTO "location_user_option" (id, location_id, user_id, pan_x, pan_y, zoom_display, active_layer_id) SELECT id, location_id, user_id, pan_x, pan_y, zoom_display, active_layer_id FROM _location_user_option_72'
            )
    elif version == 73:
        # Change Room.logo on_delete logic from cascade to set null
        with db.atomic():
            db.execute_sql("CREATE TEMPORARY TABLE _shape_73 AS SELECT * FROM shape")
            db.execute_sql("DROP TABLE shape")
            db.execute_sql(
                'CREATE TABLE IF NOT EXISTS "shape" ("uuid" TEXT NOT NULL PRIMARY KEY, "layer_id" INTEGER NOT NULL, "type_" TEXT NOT NULL, "x" REAL NOT NULL, "y" REAL NOT NULL, "name" TEXT, "name_visible" INTEGER NOT NULL, "fill_colour" TEXT NOT NULL, "stroke_colour" TEXT NOT NULL, "vision_obstruction" INTEGER NOT NULL, "movement_obstruction" INTEGER NOT NULL, "is_token" INTEGER NOT NULL, "annotation" TEXT NOT NULL, "draw_operator" TEXT NOT NULL, "index" INTEGER NOT NULL, "options" TEXT, "badge" INTEGER NOT NULL, "show_badge" INTEGER NOT NULL, "default_edit_access" INTEGER NOT NULL, "default_vision_access" INTEGER NOT NULL, is_invisible INTEGER NOT NULL DEFAULT 0, default_movement_access INTEGER NOT NULL DEFAULT 0, is_locked INTEGER NOT NULL DEFAULT 0, angle REAL NOT NULL DEFAULT 0, stroke_width INTEGER NOT NULL DEFAULT 2, asset_id INTEGER, group_id TEXT, annotation_visible INTEGER NOT NULL DEFAULT 0, ignore_zoom_size INTEGER DEFAULT 0, is_defeated INTEGER NOT NULL DEFAULT 0, is_door INTEGER DEFAULT 0 NOT NULL, is_teleport_zone INTEGER DEFAULT 0 NOT NULL, FOREIGN KEY ("layer_id") REFERENCES "layer" ("id") ON DELETE CASCADE, FOREIGN KEY ("asset_id") REFERENCES "asset" ("id") ON DELETE SET NULL, FOREIGN KEY ("group_id") REFERENCES "group" ("uuid"));'
            )
            db.execute_sql(
                'INSERT INTO "shape" ("uuid", "layer_id", "type_", "x", "y", "name", "name_visible", "fill_colour", "stroke_colour", "vision_obstruction", "movement_obstruction", "is_token", "annotation", "draw_operator", "index", "options", "badge", "show_badge", "default_edit_access", "default_vision_access", "is_invisible", "default_movement_access", "is_locked", "angle", "stroke_width", "asset_id", "group_id", "annotation_visible", "ignore_zoom_size", "is_defeated", "is_door", "is_teleport_zone") SELECT "uuid", "layer_id", "type_", "x", "y", "name", "name_visible", "fill_colour", "stroke_colour", "vision_obstruction", "movement_obstruction", "is_token", "annotation", "draw_operator", "index", "options", "badge", "show_badge", "default_edit_access", "default_vision_access", "is_invisible", "default_movement_access", "is_locked", "angle", "stroke_width", "asset_id", "group_id", "annotation_visible", "ignore_zoom_size", "is_defeated", "is_door", "is_teleport_zone" FROM _shape_73'
            )
            db.execute_sql("DROP TABLE _shape_73")
    elif version == 74:
        # Just an initiative fixer
        with db.atomic():
            db_data = db.execute_sql("SELECT id, data FROM initiative")
            for row in db_data.fetchall():
                _id, raw_data = row
                initiative_data: List[Any] = json.loads(raw_data)
                modified = False
                for index, info in reversed(list(enumerate(initiative_data))):
                    if (
                        db.execute_sql(
                            "SELECT EXISTS(SELECT 1 FROM shape WHERE uuid=?)",
                            (info["shape"],),
                        ).fetchone()[0]
                        == 0
                    ):
                        initiative_data.pop(index)
                        modified = True
                if modified:
                    db.execute_sql(
                        "UPDATE initiative SET data=? WHERE id=?",
                        (json.dumps(initiative_data), _id),
                    )
    elif version == 75:
        # Cleanup of background null values for default locations
        with db.atomic():
            db.execute_sql(
                "UPDATE location_options SET air_map_background = 'none' WHERE id IN (SELECT default_options_id FROM room) AND (air_map_background IS NULL OR air_map_background = 'rgba(0, 0, 0, 0)')"
            )
            db.execute_sql(
                "UPDATE location_options SET ground_map_background = 'none' WHERE id IN (SELECT default_options_id FROM room) AND (ground_map_background IS NULL OR ground_map_background = 'rgba(0, 0, 0, 0)')"
            )
            db.execute_sql(
                "UPDATE location_options SET underground_map_background = 'none' WHERE id IN (SELECT default_options_id FROM room) AND (underground_map_background IS NULL OR underground_map_background = 'rgba(0, 0, 0, 0)')"
            )
    elif version == 76:
        # Add UserOptions.render_all_floors
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE user_options ADD COLUMN render_all_floors INTEGER DEFAULT 1"
            )
            db.execute_sql(
                "UPDATE user_options SET render_all_floors = NULL WHERE id NOT IN (SELECT default_options_id FROM user)"
            )
    elif version == 77:
        # Add UserOptions.use_tool_icons
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE user_options ADD COLUMN use_tool_icons INTEGER DEFAULT 1"
            )
            db.execute_sql(
                "UPDATE user_options SET use_tool_icons = NULL WHERE id NOT IN (SELECT default_options_id FROM user)"
            )
    elif version == 78:
        # Add UserOptions.default_tracker_mode
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE user_options ADD COLUMN default_tracker_mode INTEGER DEFAULT 1"
            )
            db.execute_sql(
                "UPDATE user_options SET default_tracker_mode = NULL WHERE id NOT IN (SELECT default_options_id FROM user)"
            )
    elif version == 79:
        # Add UserOptions.show_token_directions
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE user_options ADD COLUMN show_token_directions INTEGER DEFAULT 1"
            )
            db.execute_sql(
                "UPDATE user_options SET show_token_directions = NULL WHERE id NOT IN (SELECT default_options_id FROM user)"
            )
    elif version == 80:
        # Add UserOptions.mouse_pan_mode
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE user_options ADD COLUMN mouse_pan_mode INTEGER DEFAULT 3"
            )
            db.execute_sql(
                "UPDATE user_options SET mouse_pan_mode = NULL WHERE id NOT IN (SELECT default_options_id FROM user)"
            )
    elif version == 81:
        # Double check UserOption modifications (lg related)
        with db.atomic():
            for option in [
                "render_all_floors",
                "use_tool_icons",
                "default_tracker_mode",
                "show_token_directions",
                "mouse_pan_mode",
            ]:
                try:
                    db.execute_sql(f"SELECT {option} FROM user_options")
                except:
                    logger.warning(f"PATCHING {option}")
                    default = 1
                    if option == "mouse_pan_mode":
                        default = 3
                    db.execute_sql(
                        f"ALTER TABLE user_options ADD COLUMN {option} INTEGER DEFAULT {default}"
                    )
                    db.execute_sql(
                        f"UPDATE user_options SET {option} = NULL WHERE id NOT IN (SELECT default_options_id FROM user)"
                    )
    elif version == 82:
        # Fix spawn-location issues
        with db.atomic():
            data = db.execute_sql(
                "SELECT lo.id, lo.spawn_locations, l.id FROM location_options lo INNER JOIN location l ON l.options_id = lo.id"
            )
            for lo_id, spawn_locations, l_id in data.fetchall():
                if spawn_locations is None or spawn_locations == "[]":
                    continue

                unpacked_spawn_locations = json.loads(spawn_locations)
                changed = False

                shape_data = db.execute_sql(
                    "SELECT s.uuid, s.type_, l.type_ FROM shape s INNER JOIN layer l ON s.layer_id = l.id INNER JOIN floor f ON f.id = l.floor_id WHERE f.location_id = ?",
                    (l_id,),
                )

                for shape_id, shape_type, layer_type in shape_data.fetchall():
                    if shape_type != "assetrect":
                        if shape_id in unpacked_spawn_locations:
                            # remove from spawn locations
                            unpacked_spawn_locations = [
                                sl for sl in unpacked_spawn_locations if sl != shape_id
                            ]
                            changed = True
                            continue
                    else:
                        shape_src_data = db.execute_sql(
                            "SELECT src FROM asset_rect WHERE shape_id=?",
                            (shape_id,),
                        ).fetchone()
                        if not shape_src_data:
                            continue
                        shape_src = shape_src_data[0]
                        if not shape_src.endswith("/static/img/spawn.png"):
                            if shape_id in unpacked_spawn_locations:
                                # remove from spawn locations
                                unpacked_spawn_locations = [
                                    sl
                                    for sl in unpacked_spawn_locations
                                    if sl != shape_id
                                ]
                                changed = True
                        elif (
                            layer_type != "dm"
                            and shape_id not in unpacked_spawn_locations
                        ):
                            # add to spawn locations
                            unpacked_spawn_locations.append(shape_id)
                            changed = True

                if changed:
                    db.execute_sql(
                        "UPDATE location_options SET spawn_locations=? WHERE id=?",
                        (json.dumps(unpacked_spawn_locations), lo_id),
                    )
    elif version == 83:
        # Add Initiative.is_active
        # Add UserOptions.initiative_open_on_activate
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE initiative ADD COLUMN is_active INTEGER DEFAULT 0 NOT NULL"
            )
            db.execute_sql(
                "ALTER TABLE user_options ADD COLUMN initiative_open_on_activate INTEGER DEFAULT 1"
            )
            db.execute_sql(
                "UPDATE user_options SET initiative_open_on_activate = NULL WHERE id NOT IN (SELECT default_options_id FROM user)"
            )
    elif version == 84:
        # Add LocationOptions.limit_movement_during_initiative
        with db.atomic():
            db.execute_sql(
                "ALTER TABLE location_options ADD COLUMN limit_movement_during_initiative INTEGER DEFAULT 0"
            )
            db.execute_sql(
                "UPDATE location_options SET limit_movement_during_initiative = NULL WHERE id NOT IN (SELECT default_options_id FROM room)"
            )
    else:
        raise UnknownVersionException(
            f"No upgrade code for save format {version} was found."
        )
    inc_save_version(db)
    db.foreign_keys = True


def upgrade_save(db: Optional[SqliteExtDatabase] = None, *, is_import=False):
    if db is None:
        db = ACTIVE_DB
    try:
        save_version = get_save_version(db)
    except:
        if is_import:
            raise Exception(
                "The import save database is not correctly formatted. Failed to import"
            )
        else:
            logger.error(
                "Database does not conform to expected format. Failed to start."
            )
            sys.exit(2)

    if save_version == SAVE_VERSION:
        return
    else:
        logger.warning(
            f"Save format {save_version} does not match the required version {SAVE_VERSION}!"
        )
        logger.warning("Attempting upgrade")

    while save_version != SAVE_VERSION:
        if not is_import:
            backup_save(save_version)

        if is_import:
            logger.warning(f"Upgrading import save to {save_version + 1}")
        else:
            logger.warning(f"Starting upgrade to {save_version + 1}")
        try:
            upgrade(db, save_version)
        except Exception as e:
            logger.exception(e)
            if is_import:
                logger.error("ERROR: Failed to upgrade import save")
            else:
                logger.error("ERROR: Could not start server")
                sys.exit(2)
        else:
            logger.warning(f"Upgrade to {save_version + 1} done.")
            save_version = get_save_version(db)
    logger.warning("Upgrade process completed successfully.")


def backup_save(version: int):
    save_backups = FILE_DIR / "save_backups"
    if not save_backups.is_dir():
        save_backups.mkdir()
    backup_path = save_backups.resolve() / f"{Path(SAVE_FILE).name}.{version}"
    logger.warning(f"Backing up old save as {backup_path}")
    shutil.copyfile(SAVE_FILE, backup_path)
