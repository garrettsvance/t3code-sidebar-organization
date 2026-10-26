import { createFileRoute } from "@tanstack/react-router";
import { CustomSettingsPanel } from "../components/settings/CustomSettingsPanel";

export const Route = createFileRoute("/_chat/settings/custom")({
  component: CustomSettingsPanel,
});
