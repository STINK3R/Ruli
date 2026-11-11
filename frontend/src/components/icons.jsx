const base = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

const icon = (paths) =>
  function Icon(props) {
    return (
      <svg {...base} {...props}>
        {paths}
      </svg>
    )
  }

export const IconPin = icon(
  <>
    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z" />
    <circle cx="12" cy="10" r="3" />
  </>,
)

export const IconFuel = icon(
  <>
    <path d="M3 22V4a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v18" />
    <path d="M2 22h12M13 9h3a2 2 0 0 1 2 2v6a2 2 0 0 0 3 1.7M18 6.5 21 9" />
  </>,
)

export const IconLocate = icon(<path d="m3 11 19-9-9 19-2-8-8-2z" />)
export const IconPlus = icon(<path d="M12 5v14M5 12h14" />)
export const IconMinus = icon(<path d="M5 12h14" />)
export const IconClose = icon(<path d="M18 6 6 18M6 6l12 12" />)
export const IconArrowLeft = icon(<path d="M19 12H5M12 19l-7-7 7-7" />)
export const IconCheck = icon(<path d="M20 6 9 17l-5-5" />)
export const IconChevron = icon(<path d="m9 18 6-6-6-6" />)

export const IconInfo = icon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 16v-4M12 8h.01" />
  </>,
)

export const IconRefresh = icon(
  <>
    <path d="M21 12a9 9 0 1 1-2.64-6.36" />
    <path d="M21 3v6h-6" />
  </>,
)

export const IconWalk = icon(
  <>
    <circle cx="13" cy="4" r="2" />
    <path d="m9 21 2.5-6.5L14 17v4M7 12l2.5-4.5 4 1.5 2 3 2.5 1" />
  </>,
)

export const IconAlert = icon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v4M12 16h.01" />
  </>,
)

export const IconClock = icon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </>,
)

export const IconCar = icon(
  <>
    <path d="M5 17H3v-5l2-5h14l2 5v5h-2" />
    <circle cx="7.5" cy="17" r="2" />
    <circle cx="16.5" cy="17" r="2" />
    <path d="M9.5 17h5" />
  </>,
)

export const IconGearbox = icon(
  <>
    <circle cx="6" cy="6" r="2" />
    <circle cx="12" cy="6" r="2" />
    <circle cx="18" cy="6" r="2" />
    <circle cx="6" cy="18" r="2" />
    <circle cx="12" cy="18" r="2" />
    <path d="M6 8v8M12 8v8M18 8v4H6" />
  </>,
)

export const IconEngine = icon(
  <>
    <path d="M4 9h3l2-3h6v3h2l2 2v6h-2v2h-4l-2-2H7l-1-2H4z" />
    <path d="M2 11v5" />
  </>,
)

export const IconSeat = icon(
  <>
    <path d="M7 4h4l1 9h6l1 6H8z" />
    <path d="M5 19h15" />
  </>,
)

export const IconSpark = icon(<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />)

export const IconShield = icon(<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />)

export const IconRoute = icon(
  <>
    <circle cx="6" cy="19" r="3" />
    <circle cx="18" cy="5" r="3" />
    <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15" />
  </>,
)

export const IconLock = icon(
  <>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </>,
)

export const IconCamera = icon(
  <>
    <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
    <circle cx="12" cy="13" r="3.5" />
  </>,
)

export const IconSeal = icon(
  <>
    <circle cx="12" cy="10" r="6" />
    <path d="m9 15.5-1.5 6L12 19l4.5 2.5-1.5-6" />
  </>,
)

export const IconDocument = icon(
  <>
    <path d="M7 3h7l4 4v14H7z" />
    <path d="M14 3v4h4M10 12h5M10 16h5" />
  </>,
)

export const IconShare = icon(
  <>
    <path d="M12 3v12M8 7l4-4 4 4" />
    <path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1" />
  </>,
)

export const IconPlusSquare = icon(
  <>
    <rect x="3.5" y="3.5" width="17" height="17" rx="4" />
    <path d="M12 8v8M8 12h8" />
  </>,
)

export const IconDots = icon(
  <>
    <circle cx="12" cy="5" r="1.3" fill="currentColor" />
    <circle cx="12" cy="12" r="1.3" fill="currentColor" />
    <circle cx="12" cy="19" r="1.3" fill="currentColor" />
  </>,
)

export const IconDownload = icon(<path d="M12 4v11M7 10l5 5 5-5M5 20h14" />)

export const IconSun = icon(
  <>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </>,
)

export const IconMoon = icon(<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" />)

export const IconAuto = icon(
  <>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 3.5v17a8.5 8.5 0 0 0 0-17z" fill="currentColor" />
  </>,
)

export const IconUser = icon(
  <>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
  </>,
)

export const IconMap = icon(
  <>
    <path d="M9 4 3 6.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z" />
    <path d="M9 4v13.5M15 6.5V20" />
  </>,
)

export const IconSearch = icon(
  <>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m20 20-4.2-4.2" />
  </>,
)

export const IconFlag = icon(<path d="M5 21V4M5 4h11l-2 4 2 4H5" />)

export const IconPhone = icon(
  <>
    <rect x="6.5" y="2.5" width="11" height="19" rx="3" />
    <path d="M10.5 18.5h3" />
  </>,
)

export const IconFace = icon(
  <>
    <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" />
    <path d="M9 10v1M15 10v1M9.5 15c1.5 1.2 3.5 1.2 5 0" />
  </>,
)

export const IconMore = icon(
  <>
    <rect x="4" y="4" width="6" height="6" rx="1.5" />
    <rect x="14" y="4" width="6" height="6" rx="1.5" />
    <rect x="4" y="14" width="6" height="6" rx="1.5" />
    <rect x="14" y="14" width="6" height="6" rx="1.5" />
  </>,
)

export const IconBolt = icon(<path d="M13 2 4 14h7l-1 8 9-12h-7z" />)

export const IconSwitchCamera = icon(
  <>
    <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
    <path d="M9 13a3 3 0 0 1 5.2-2M15 13a3 3 0 0 1-5.2 2M14 9.5v1.7h-1.7M10 16.5v-1.7h1.7" />
  </>,
)

export const IconLogout = icon(<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" />)

export const IconHelp = icon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01" />
  </>,
)
