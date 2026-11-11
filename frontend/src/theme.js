// «Рули Street»: цвета для JavaScript (карта, маркеры, SVG машин). Интерфейс берёт
// те же значения из CSS-переменных (styles/tokens.css). Карта — своя для каждой темы:
// «Ночь» — мокрый асфальт с кобальтовой водой, «День» — светлый бетон.
const MAPS = {
  night: {
    land: '#15161c',
    water: '#10207a',
    waterLabel: '#8ea0ff',
    park: '#1a1b22',
    building: '#20222b',
    roadMajor: '#363a48',
    roadMinor: '#272a35',
    roadCasing: '#0d0e12',
    motorway: '#4b4724',
    motorwayCasing: '#0d0e12',
    railway: '#2c2f3b',
    label: '#b4b8c8',
    labelHalo: '#0d0e12',
  },
  day: {
    land: '#ebe8e1',
    water: '#a9b8f5',
    waterLabel: '#1834d6',
    park: '#dfddd5',
    building: '#dad6cc',
    roadMajor: '#ffffff',
    roadMinor: '#f7f5f0',
    roadCasing: '#cdc8bc',
    motorway: '#fff3a3',
    motorwayCasing: '#e2cf5c',
    railway: '#c8c3b8',
    label: '#3d3f48',
    labelHalo: '#f5f3ee',
  },
}

const PINS = {
  night: {
    dot: '#ffe814',
    dotStroke: '#0d0e12',
    dotBusy: '#5d6070',
    dotLocked: '#6c6f80',
    signatureCore: '#ff4fb0',
    premiumStroke: '#ff4fb0',
    selectedRing: '#ff4fb0',
    selectedGap: '#0d0e12',
    halo: 'rgba(255,232,20,1)',
    clusterText: '#0d0e12',
    clusterStroke: 'rgba(13,14,18,0.9)',
    priceBg: '#0d0e12',
    priceStroke: 'rgba(255,232,20,0.55)',
    priceText: '#ffe814',
    priceSelectedBg: '#ff4fb0',
    priceSelectedText: '#ffffff',
    routeCasing: '#0d0e12',
    routeLine: '#ffe814',
    tripLine: '#ff4fb0',
    userDot: '#2a4bff',
  },
  day: {
    dot: '#1834d6',
    dotStroke: '#ffffff',
    dotBusy: '#a4a3a0',
    dotLocked: '#b8b6b0',
    signatureCore: '#ffe814',
    premiumStroke: '#ff4fb0',
    selectedRing: '#ff4fb0',
    selectedGap: '#ffffff',
    halo: 'rgba(24,52,214,1)',
    clusterText: '#ffffff',
    clusterStroke: 'rgba(255,232,20,0.9)',
    priceBg: '#0d0e12',
    priceStroke: 'rgba(13,14,18,0.2)',
    priceText: '#ffe814',
    priceSelectedBg: '#ffe814',
    priceSelectedText: '#0d0e12',
    routeCasing: '#ffffff',
    routeLine: '#1834d6',
    tripLine: '#d92c8c',
    userDot: '#ff4fb0',
  },
}

export function mapPalette(theme) {
  return MAPS[theme] || MAPS.night
}

export function pinPalette(theme) {
  return PINS[theme] || PINS.night
}

export const THEME = {
  // Ливреи Signature: оклейка в стиле граффити, «тег» на крыше виден сверху лучше всего.
  livery: {
    graphite: {
      light: '#3b3e4a', body: '#15161c', dark: '#050608',
      roof: '#ffe814', roofDark: '#d9c200', mono: '#0d0e12', mirror: '#ff4fb0', tag: '#ff4fb0',
    },
    ivory: {
      light: '#ffffff', body: '#f1f0ec', dark: '#c4c1b8',
      roof: '#1834d6', roofDark: '#0c1c8c', mono: '#ffe814', mirror: '#ffe814', tag: '#ff4fb0',
    },
  },
}
