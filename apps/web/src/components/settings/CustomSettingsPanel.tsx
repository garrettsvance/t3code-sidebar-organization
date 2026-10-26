import { DEFAULT_CLIENT_SETTINGS } from "@t3tools/contracts/settings";
import { persistClientSettingsPatch, useClientSettings } from "../../hooks/useSettings";
import { Switch } from "../ui/switch";
import {
  SettingResetButton,
  SettingsPageContainer,
  SettingsRow,
  SettingsSection,
} from "./settingsLayout";
import { searchableSetting } from "./settingsSearch";

export function CustomSettingsPanel() {
  const settings = useClientSettings();
  const updateSettings = persistClientSettingsPatch;
  return (
    <SettingsPageContainer>
      <SettingsSection id="custom" title="Custom">
        <SettingsRow
          {...searchableSetting("custom-settings")}
          description="Enable this build's custom sidebar features and Custom label. Turning this off preserves your individual settings. This build is updated with the Sidebar updater, rather than the stable or nightly update track."
          resetAction={
            settings.customSettingsEnabled !== DEFAULT_CLIENT_SETTINGS.customSettingsEnabled ? (
              <SettingResetButton
                label="custom settings"
                onClick={() =>
                  void updateSettings({
                    customSettingsEnabled: DEFAULT_CLIENT_SETTINGS.customSettingsEnabled,
                  })
                }
              />
            ) : null
          }
          control={
            <Switch
              checked={settings.customSettingsEnabled}
              onCheckedChange={(checked) =>
                void updateSettings({ customSettingsEnabled: Boolean(checked) })
              }
              aria-label="Custom settings"
            />
          }
        />
        <SettingsRow
          {...searchableSetting("group-by-project")}
          description="Group active threads under a colored header for their project. Drag a header to move its group. Active threads can't be dragged while this is on."
          resetAction={
            settings.sidebarGroupByProject !== DEFAULT_CLIENT_SETTINGS.sidebarGroupByProject ? (
              <SettingResetButton
                label="group by project"
                onClick={() =>
                  updateSettings({
                    sidebarGroupByProject: DEFAULT_CLIENT_SETTINGS.sidebarGroupByProject,
                  })
                }
              />
            ) : null
          }
          control={
            <Switch
              disabled={!settings.customSettingsEnabled}
              checked={settings.sidebarGroupByProject}
              onCheckedChange={(checked) =>
                updateSettings({ sidebarGroupByProject: Boolean(checked) })
              }
              aria-label="Group by project"
            />
          }
        />

        <SettingsRow
          {...searchableSetting("project-attention-indicator")}
          description="Show an exclamation mark on a project header when an active thread needs input or approval. Requires Group by project."
          resetAction={
            settings.sidebarProjectAttentionIndicator !==
            DEFAULT_CLIENT_SETTINGS.sidebarProjectAttentionIndicator ? (
              <SettingResetButton
                label="project attention indicator"
                onClick={() =>
                  updateSettings({
                    sidebarProjectAttentionIndicator:
                      DEFAULT_CLIENT_SETTINGS.sidebarProjectAttentionIndicator,
                  })
                }
              />
            ) : null
          }
          control={
            <Switch
              disabled={!settings.customSettingsEnabled}
              checked={settings.sidebarProjectAttentionIndicator}
              onCheckedChange={(checked) =>
                updateSettings({ sidebarProjectAttentionIndicator: Boolean(checked) })
              }
              aria-label="Project attention indicator"
            />
          }
        />

        <SettingsRow
          {...searchableSetting("sort-by-status")}
          description="In the Active section, list threads that need your input first, then finished threads, then threads that are still working. Active threads can't be dragged while this is on."
          resetAction={
            settings.sidebarSortByStatus !== DEFAULT_CLIENT_SETTINGS.sidebarSortByStatus ? (
              <SettingResetButton
                label="sort by status"
                onClick={() =>
                  updateSettings({
                    sidebarSortByStatus: DEFAULT_CLIENT_SETTINGS.sidebarSortByStatus,
                  })
                }
              />
            ) : null
          }
          control={
            <Switch
              disabled={!settings.customSettingsEnabled}
              checked={settings.sidebarSortByStatus}
              onCheckedChange={(checked) =>
                updateSettings({ sidebarSortByStatus: Boolean(checked) })
              }
              aria-label="Sort by status"
            />
          }
        />
      </SettingsSection>
    </SettingsPageContainer>
  );
}
