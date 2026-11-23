import { useGT } from "gt-react";
import { DEFAULT_CLIENT_SETTINGS } from "@t3tools/contracts/settings";
import { persistClientSettingsPatch, useClientSettings } from "../../hooks/useSettings";
import { Switch } from "../ui/switch";
import {
  SettingResetButton,
  SettingsPageContainer,
  SettingsRow,
  SettingsSection,
} from "./settingsLayout";
import { useSearchableSetting } from "./settingsSearch";

export function CustomSettingsPanel() {
  const gt = useGT();
  const searchableSetting = useSearchableSetting();
  const settings = useClientSettings();
  const updateSettings = persistClientSettingsPatch;
  return (
    <SettingsPageContainer>
      <SettingsSection id="custom" title={gt("Custom")}>
        <SettingsRow
          {...searchableSetting("custom-settings")}
          description={gt(
            "Enable this build's custom sidebar features and Custom label. Turning this off preserves your individual settings. Custom builds do not receive stable or nightly updates.",
          )}
          resetAction={
            settings.customSettingsEnabled !== DEFAULT_CLIENT_SETTINGS.customSettingsEnabled ? (
              <SettingResetButton
                ariaLabel={gt("Reset custom settings to default")}
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
              aria-label={gt("Custom settings")}
            />
          }
        />
        <SettingsRow
          {...searchableSetting("group-by-project")}
          description={gt("Group active threads under a colored header for their project.")}
          resetAction={
            settings.sidebarGroupByProject !== DEFAULT_CLIENT_SETTINGS.sidebarGroupByProject ? (
              <SettingResetButton
                ariaLabel={gt("Reset group by project to default")}
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
              aria-label={gt("Group by project")}
            />
          }
        />

        <SettingsRow
          {...searchableSetting("fixed-group-location")}
          description={gt(
            "Keep project groups in your saved order and drag their headers to rearrange them. When off, groups and their chats follow your most recent sends.",
          )}
          resetAction={
            settings.sidebarFixedGroupLocation !==
            DEFAULT_CLIENT_SETTINGS.sidebarFixedGroupLocation ? (
              <SettingResetButton
                ariaLabel={gt("Reset fixed group location to default")}
                onClick={() =>
                  updateSettings({
                    sidebarFixedGroupLocation: DEFAULT_CLIENT_SETTINGS.sidebarFixedGroupLocation,
                  })
                }
              />
            ) : null
          }
          control={
            <Switch
              disabled={!settings.customSettingsEnabled || !settings.sidebarGroupByProject}
              checked={settings.sidebarFixedGroupLocation}
              onCheckedChange={(checked) =>
                updateSettings({ sidebarFixedGroupLocation: Boolean(checked) })
              }
              aria-label={gt("Fixed Group Location")}
            />
          }
        />

        <SettingsRow
          {...searchableSetting("project-attention-indicator")}
          description={gt(
            "Show an exclamation mark on a project header when an active thread needs input or approval. Requires Group by project.",
          )}
          resetAction={
            settings.sidebarProjectAttentionIndicator !==
            DEFAULT_CLIENT_SETTINGS.sidebarProjectAttentionIndicator ? (
              <SettingResetButton
                ariaLabel={gt("Reset project attention indicator to default")}
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
              aria-label={gt("Project attention indicator")}
            />
          }
        />

        <SettingsRow
          {...searchableSetting("sort-by-status")}
          description={gt(
            "List threads that need your input first, then finished threads, then working threads. Applies when project grouping is off or Fixed Group Location is on.",
          )}
          resetAction={
            settings.sidebarSortByStatus !== DEFAULT_CLIENT_SETTINGS.sidebarSortByStatus ? (
              <SettingResetButton
                ariaLabel={gt("Reset sort by status to default")}
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
              aria-label={gt("Sort by status")}
            />
          }
        />
      </SettingsSection>
    </SettingsPageContainer>
  );
}
