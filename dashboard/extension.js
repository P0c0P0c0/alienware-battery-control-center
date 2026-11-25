import Meta from 'gi://Meta';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const APP = 'io.github.bat07.Widget';

export default class BatteryWidget extends Extension {
    enable() {
        this.windows = new WeakSet();
        this.mapId = global.window_manager.connect_after('map', (_manager, actor) =>
            this.addWindow(actor.meta_window));
        for (const actor of global.get_window_actors())
            this.addWindow(actor.meta_window);
    }

    addWindow(window) {
        if (!window || window.get_window_type() !== Meta.WindowType.NORMAL ||
            (window.get_gtk_application_id() !== APP && window.get_wm_class() !== APP))
            return;
        window.make_above();
        if (this.windows.has(window))
            return;
        this.windows.add(window);
        const monitor = global.display.get_primary_monitor();
        const workspace = global.workspace_manager.get_active_workspace();
        const area = workspace.get_work_area_for_monitor(monitor);
        const frame = window.get_frame_rect();
        window.move_frame(false, Math.max(area.x, area.x + area.width - frame.width - 16),
            area.y + 16);
    }

    disable() {
        global.window_manager.disconnect(this.mapId);
        for (const actor of global.get_window_actors()) {
            if (this.windows.has(actor.meta_window))
                actor.meta_window.unmake_above();
        }
        this.windows = null;
    }
}
