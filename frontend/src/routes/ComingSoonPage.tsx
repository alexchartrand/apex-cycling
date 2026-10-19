import { useTranslation } from "react-i18next";
import { EmptyState, PageHeader } from "../components/ui";
import { NAV_ITEMS, type NavKey } from "../components/shell/navigation";

type ComingSoonSection = Exclude<NavKey, "home" | "progress" | "import">;

/** Placeholder for a roadmap section that isn't built yet (see BACKLOG.md). */
export function ComingSoonPage({ section }: { section: ComingSoonSection }) {
  const { t } = useTranslation("shell");
  const Icon = NAV_ITEMS[section].icon;
  return (
    <>
      <PageHeader title={t(`nav.${section}`)} />
      <EmptyState
        icon={<Icon aria-hidden />}
        title={t("comingSoon.badge")}
        description={t(`comingSoon.${section}`)}
      />
    </>
  );
}
