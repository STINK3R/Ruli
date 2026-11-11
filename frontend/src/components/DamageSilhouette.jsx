import { carTopViewSvg } from '../utils/carVisual'

/**
 * Крупный силуэт машины вид сверху с отметками повреждений.
 * Координаты отметок — доли ширины и длины силуэта (0–1), как в API.
 */
export default function DamageSilhouette({ car, damages = [], marks = [], onAdd, onPick, activeId }) {
  const handleClick = (event) => {
    if (!onAdd) return
    const box = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - box.left) / box.width
    const y = (event.clientY - box.top) / box.height
    onAdd({ x: Math.round(x * 1000) / 1000, y: Math.round(y * 1000) / 1000 })
  }

  return (
    <div className={`silhouette ${onAdd ? 'silhouette--editable' : ''}`}>
      <div className="silhouette__car" onClick={handleClick}>
        <span dangerouslySetInnerHTML={{ __html: carTopViewSvg(car, { width: 150 }) }} />
        {damages.map((damage) => (
          <button
            key={`d${damage.id}`}
            type="button"
            className={`pin pin--${damage.status} ${activeId === damage.id ? 'is-active' : ''}`}
            style={{ left: `${damage.x * 100}%`, top: `${damage.y * 100}%` }}
            onClick={(event) => {
              event.stopPropagation()
              onPick?.(damage)
            }}
            title={damage.severity_display}
          />
        ))}
        {marks.map((mark, index) => (
          <button
            key={`m${index}`}
            type="button"
            className="pin pin--mark"
            style={{ left: `${mark.x * 100}%`, top: `${mark.y * 100}%` }}
            onClick={(event) => {
              event.stopPropagation()
              onPick?.(mark, index)
            }}
            title="Новая отметка — нажмите, чтобы убрать"
          />
        ))}
      </div>
      <span className="silhouette__label silhouette__label--front">Перед</span>
      <span className="silhouette__label silhouette__label--rear">Зад</span>
    </div>
  )
}
