export default {
  greeting: {
    morning: "Good morning, {{name}}",
    afternoon: "Good afternoon, {{name}}",
    evening: "Good evening, {{name}}",
  },
  week: {
    sessions: "Sessions this week",
    laps: "Laps this week",
    distance: "{{distance}} on track",
    trackTime: "Time on track",
    vsLastWeek: "vs last week",
  },
  latest: {
    eyebrow: "Latest session",
    open: "Open",
    tracks: "Tracks",
  },
  recent: { title: "Recent sessions", viewAll: "View all" },
  sync: {
    title: "Sync",
    lastSync: "Last sync {{when}}",
    never: "No sync yet",
    failed: "Last sync failed",
    activeTransponders_one: "{{count}} transponder syncing automatically",
    activeTransponders_other: "{{count}} transponders syncing automatically",
    noActive: "No transponder is syncing automatically.",
    manage: "Manage imports",
  },
  checklist: {
    eyebrow: "Getting started",
    title: "Set up ApexCycling",
    progress: "{{done}} of {{total}}",
    optional: "optional",
    done: "done",
    hide: "Hide this checklist",
    steps: {
      transponder: {
        title: "Connect your transponder",
        hint: "Your laps are imported after every session.",
        action: "Connect",
      },
      physiology: {
        title: "Add your weight and FTP",
        hint: "Weight gives W/kg and the aero lab; FTP only matters if you train with power.",
        action: "Add",
      },
      club: { title: "Join your club", hint: "Paste an invitation link, or create the club.", action: "Open clubs" },
      coach: { title: "Choose a coach", hint: "A coach can follow your sessions and plan the next ones.", action: "Find a coach" },
    },
  },
  onboarding: {
    title: "Welcome to ApexCycling",
    description: "Connect the sqorz transponder you ride with and your laps will be imported automatically after every session.",
    action: "Connect a transponder",
  },
};
