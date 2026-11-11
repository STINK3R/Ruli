const CAR_CLASSES = [
  ['', 'Все'],
  ['economy', 'Эконом'],
  ['comfort', 'Комфорт'],
  ['business', 'Бизнес'],
  ['premium', 'Премиум'],
]

export default function FilterChips({ filters, onChange }) {
  return (
    <div className="chips chips--scroll">
      {CAR_CLASSES.map(([value, label]) => (
        <button
          key={value || 'all'}
          type="button"
          className={`chip ${filters.car_class === value ? 'chip--active' : ''}`}
          onClick={() => onChange({ ...filters, car_class: value })}
        >
          {label}
        </button>
      ))}

      <button
        type="button"
        className={`chip chip--accent ${filters.onlyAvailable ? 'chip--active' : ''}`}
        onClick={() => onChange({ ...filters, onlyAvailable: !filters.onlyAvailable })}
      >
        Только свободные
      </button>
    </div>
  )
}
