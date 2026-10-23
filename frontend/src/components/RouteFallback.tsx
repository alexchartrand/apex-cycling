import { useTranslation } from "react-i18next";
import { SkeletonGroup } from "./ui";

/** Stands in for a page whose chunk is still downloading. */
export function RouteFallback() {
  const { t } = useTranslation("common");
  return <SkeletonGroup lines={4} label={t("loading")} />;
}
