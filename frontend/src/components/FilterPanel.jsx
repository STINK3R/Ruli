const CAR_CLASSES = [
  ['economy', 'Эконом'],
  ['comfort', 'Комфорт'],
  ['business', 'Бизнес'],
  ['premium', 'Премиум'],
]

const TRANSMISSIONS = [
  ['automatic', 'Автомат'],
  ['manual', 'Механика'],
]

const FUEL_TYPES = [
  ['petrol', 'Бензин'],
  ['diesel', 'Дизель'],
  ['hybrid', 'Гибрид'],
  ['electric', 'Электро'],
]

const ORDERINGS = [
  ['', 'Ближе всего'],
  ['tariff__price_per_minute', 'Дешевле'],
  ['-year', 'Новее'],
]

export default function FilterPanel({ filters, onChange }) {
  const update = (key) => (event) => {
    const { value, type, checked } = event.target
    onChange({ ...filters, [key]: type === 'checkbox' ? checked : value })
  }

  return (
    <div className="filters">
      <div className="field">
        <label htmlFor="ordering">Сортировка</label>
        <select id="ordering" value={filters.ordering} onChange={update('ordering')}>
          {ORDERINGS.map(([value, label]) => (
            <option key={value || 'near'} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="search">Поиск</label>
        <input
          id="search"
          type="search"
          placeholder="Марка или модель"
          value={filters.search}
          onChange={update('search')}
        />
      </div>

      <div className="field">
        <label htmlFor="car_class">Класс</label>
        <select id="car_class" value={filters.car_class} onChange={update('car_class')}>
          <option value="">Любой</option>
          {CAR_CLASSES.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="transmission">Коробка</label>
        <select
          id="transmission"
          value={filters.transmission}
          onChange={update('transmission')}
        >
          <option value="">Любая</option>
          {TRANSMISSIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="fuel_type">Топливо</label>
        <select id="fuel_type" value={filters.fuel_type} onChange={update('fuel_type')}>
          <option value="">Любое</option>
          {FUEL_TYPES.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="max_price">Цена до, BYN/мин</label>
        <input
          id="max_price"
          type="number"
          min="0"
          step="0.05"
          placeholder="—"
          value={filters.max_price}
          onChange={update('max_price')}
        />
      </div>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={filters.onlyAvailable}
          onChange={update('onlyAvailable')}
        />
        Только свободные
      </label>
    </div>
  )
}
