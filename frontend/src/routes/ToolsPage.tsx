import { Link2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { Button, PageHeader, TabPanel, Tabs, useToast, type TabItem } from "../components/ui";
import { copyText } from "../hooks/copyText";
import { AirDensityTool } from "../features/tools/AirDensityTool";
import { GearingTool } from "../features/tools/GearingTool";
import { PowerTool } from "../features/tools/PowerTool";
import { PursuitTool } from "../features/tools/PursuitTool";
import type { NumberKey } from "../features/tools/toolInputs";
import { PURSUIT_KEYS } from "../features/tools/usePursuitSchedule";
import { AIR_KEYS, SETUP_KEYS, useToolInputs } from "../features/tools/useToolInputs";
import "./ToolsPage.css";

const SECTIONS = ["power", "pursuit", "gearing", "air"] as const;
type Section = (typeof SECTIONS)[number];

/** What each tool's share link carries. */
const SHARE: Record<Section, { keys: NumberKey[]; time?: boolean; start?: boolean; mode?: boolean }> = {
  power: { keys: ["distanceM", "powerW", ...SETUP_KEYS, ...AIR_KEYS], time: true, start: true, mode: true },
  pursuit: { keys: PURSUIT_KEYS, time: true },
  gearing: { keys: ["chainring", "cog", "rolloutM", "lapM"] },
  air: { keys: AIR_KEYS },
};

function isSection(value: string | undefined): value is Section {
  return SECTIONS.includes(value as Section);
}

export function ToolsPage() {
  const { t } = useTranslation("tools");
  const navigate = useNavigate();
  const { search } = useLocation();
  const section = useParams()["*"];
  const inputs = useToolInputs();
  const { toast } = useToast();

  if (!isSection(section)) return <Navigate to={`/tools/power${search}`} replace />;

  const items: TabItem<Section>[] = SECTIONS.map((value) => ({ value, label: t(`sections.${value}`) }));

  const share = async () => {
    const { keys, ...extra } = SHARE[section];
    const url = `${window.location.origin}/tools/${section}?${inputs.shareSearch(keys, extra)}`;
    toast((await copyText(url)) ? { title: t("page.shared"), tone: "success" } : { title: t("page.shareFailed"), tone: "error" });
  };

  return (
    <>
      <PageHeader
        title={t("page.title")}
        description={t("page.description")}
        actions={
          <Button variant="secondary" icon={<Link2 aria-hidden />} onClick={share}>
            {t("page.share")}
          </Button>
        }
      />
      <div className="tools-page">
        {/* Inputs are shared by the tools, so switching keeps the query string. */}
        <Tabs items={items} value={section} onValueChange={(next) => navigate(`/tools/${next}${search}`)} aria-label={t("page.title")}>
          <TabPanel value="power">
            <PowerTool inputs={inputs} />
          </TabPanel>
          <TabPanel value="pursuit">
            <PursuitTool inputs={inputs} />
          </TabPanel>
          <TabPanel value="gearing">
            <GearingTool inputs={inputs} />
          </TabPanel>
          <TabPanel value="air">
            <AirDensityTool inputs={inputs} />
          </TabPanel>
        </Tabs>
      </div>
    </>
  );
}
