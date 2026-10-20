import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/errors";
import { Card, PageHeader, TabPanel, Tabs, useToast, type TabItem } from "../components/ui";
import { AskByEmail } from "../features/coaching/AskByEmail";
import { AthleteCards } from "../features/coaching/AthleteCards";
import { MyCoaches } from "../features/coaching/MyCoaches";
import { useCoachedAthletes, useRequestCoachLink } from "../features/coaching/useCoaching";
import { WaitingForYou } from "../features/coaching/WaitingForYou";
import "../features/coaching/Coaching.css";

const TABS = ["athletes", "coaches"] as const;
type CoachTab = (typeof TABS)[number];

const isTab = (value: string | null): value is CoachTab => TABS.includes(value as CoachTab);

/** Coaching in both directions: the athletes I coach (dashboard) and the coaches I have. */
export function CoachPage() {
  const { t } = useTranslation("coach");
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get("tab");
  const tab: CoachTab = isTab(requested) ? requested : "athletes";
  const request = useRequestCoachLink();
  const coached = useCoachedAthletes();

  const items: TabItem<CoachTab>[] = [
    { value: "athletes", label: t("tabs.athletes"), count: coached.data?.filter((link) => link.status === "active").length },
    { value: "coaches", label: t("tabs.coaches") },
  ];

  async function askToCoach(email: string) {
    try {
      await request.mutateAsync({ acting_as: "coach", athlete_email: email });
      // Same wording whether or not the address has an account: the backend doesn't say either.
      toast({ title: t("ask.sent"), description: t("ask.sentHint"), tone: "success" });
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="coach-stack">
        <WaitingForYou />
        <Tabs
          items={items}
          value={tab}
          onValueChange={(next) => setSearchParams(next === "athletes" ? {} : { tab: next }, { replace: true })}
          aria-label={t("tabs.label")}
        >
          <TabPanel value="athletes">
            <div className="coach-stack">
              <AthleteCards />
              <Card as="section" title={t("ask.title")}>
                <div className="coach-stack">
                  <p className="coach-muted">{t("ask.description")}</p>
                  <AskByEmail
                    label={t("ask.athleteEmail")}
                    action={t("ask.action")}
                    pending={request.isPending}
                    onSubmit={askToCoach}
                  />
                </div>
              </Card>
            </div>
          </TabPanel>
          <TabPanel value="coaches">
            <MyCoaches />
          </TabPanel>
        </Tabs>
      </div>
    </>
  );
}
