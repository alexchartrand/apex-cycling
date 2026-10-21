import { useTranslation } from "react-i18next";
import { EmptyState, PageHeader, Skeleton } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { EquipmentPanel } from "../features/equipment/EquipmentPanel";
import "./EquipmentPage.css";

export function EquipmentPage() {
  const { t } = useTranslation("equipment");
  const { t: tc } = useTranslation("common");
  const athlete = useActiveAthlete();

  return (
    <>
      <PageHeader title={t("title")} />
      <div className="equipment-page">
        {athlete.data ? (
          <EquipmentPanel athleteId={athlete.data.id} />
        ) : athlete.isError ? (
          <EmptyState compact title={tc("loadError")} />
        ) : (
          <Skeleton height="12rem" />
        )}
      </div>
    </>
  );
}
