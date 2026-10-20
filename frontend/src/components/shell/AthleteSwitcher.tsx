import { Check, ChevronsUpDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useActiveAthlete } from "../../features/athletes/useActiveAthlete";
import { useSwitchOptions } from "../../features/athletes/useSwitchOptions";
import { setViewingAthleteId } from "../../features/athletes/viewing";
import type { SwitchGroup, SwitchOption } from "../../features/athletes/switchOptions";
import { useMyAthlete } from "../../features/athletes/useAthlete";
import { Avatar, Button, Menu, MenuItem, MenuLabel, MenuSeparator } from "../ui";

const GROUP_ORDER: SwitchGroup[] = ["me", "coached", "club"];

/**
 * "Whose data am I looking at?" — for coaches and club admins. Renders
 * nothing for someone with nobody else to switch to.
 */
export function AthleteSwitcher({ variant }: { variant: "full" | "compact" | "avatar" }) {
  const { t } = useTranslation("shell");
  const navigate = useNavigate();
  const options = useSwitchOptions();
  const active = useActiveAthlete().data;
  const me = useMyAthlete().data;

  if (options.length < 2) return null;

  function choose(option: SwitchOption) {
    // A session or record page of one athlete means nothing for another.
    setViewingAthleteId(option.group === "me" || option.athleteId === me?.id ? null : option.athleteId);
    navigate("/");
  }

  const name = active?.display_name ?? "";
  const trigger =
    variant === "full" ? (
      <button type="button" className="shell__switcher" aria-label={t("switcher.label")}>
        <Avatar name={name} size="sm" />
        <span className="shell__switcher-text">
          <span className="shell__switcher-caption">{t("switcher.viewing")}</span>
          <span className="shell__switcher-name">{active?.id === me?.id ? t("switcher.me") : name}</span>
        </span>
        <ChevronsUpDown aria-hidden />
      </button>
    ) : (
      // A chip with a chevron, so on a phone it doesn't read as a second copy of the account avatar next to it.
      <Button variant="secondary" size="sm" className="shell__switcher-chip" aria-label={t("switcher.label")}>
        <Avatar name={name} size="sm" />
        <ChevronsUpDown aria-hidden />
      </Button>
    );

  return (
    <Menu trigger={trigger} align="start">
      {GROUP_ORDER.map((group, index) => {
        const inGroup = options.filter((option) => option.group === group);
        if (inGroup.length === 0) return null;
        return (
          <div key={group}>
            {index > 0 && <MenuSeparator />}
            <MenuLabel>{t(`switcher.groups.${group}`)}</MenuLabel>
            {inGroup.map((option) => (
              <MenuItem
                key={option.athleteId}
                icon={<Check aria-hidden style={{ visibility: option.athleteId === active?.id ? "visible" : "hidden" }} />}
                onSelect={() => choose(option)}
              >
                {option.group === "me" ? t("switcher.me") : option.name}
                {option.clubName ? ` · ${option.clubName}` : ""}
              </MenuItem>
            ))}
          </div>
        );
      })}
    </Menu>
  );
}
