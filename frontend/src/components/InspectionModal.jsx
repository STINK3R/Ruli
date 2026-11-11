import { useEffect, useRef, useState } from 'react'
import { extractError } from '../api/client'
import { usePassport, useSubmitInspection } from '../hooks/usePassport'
import { useUserLocation } from '../location/LocationContext'
import { useUi } from '../ui/UiProvider'
import { ANGLE_LABELS, makeDemoPhoto } from '../utils/demoPhotos'
import { downscaleImage } from '../utils/images'
import { plural } from '../utils/plural'
import DamageSilhouette from './DamageSilhouette'
import Modal from './Modal'
import { IconCamera } from './icons'

const SEVERITIES = [
  ['scratch', 'Царапина'],
  ['dent', 'Вмятина'],
  ['crack', 'Скол'],
]
const CLEANLINESS = [
  [1, 'Чисто'],
  [2, 'Есть мусор'],
  [3, 'Грязно'],
]
const MAX_MARKS = 12

function PhotoSlot({ angle, preview, error, onFile }) {
  return (
    <label
      className={`photo-slot photo-slot--${angle} ${preview ? 'has-photo' : ''} ${error ? 'has-error' : ''}`}
    >
      {preview ? (
        <img src={preview} alt={ANGLE_LABELS[angle]} />
      ) : (
        <>
          <IconCamera width={20} height={20} />
          <span>{ANGLE_LABELS[angle]}</span>
        </>
      )}
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        className="visually-hidden"
        aria-label={`Фото: ${ANGLE_LABELS[angle]}`}
        onChange={(event) => {
          const file = event.target.files[0]
          event.target.value = ''
          if (file) onFile(file)
        }}
      />
      {error && <small>{error}</small>}
    </label>
  )
}

export default function InspectionModal({ rental, kind, onClose, onDone }) {
  const { car } = rental
  const { data: passport } = usePassport(car.id)
  const submit = useSubmitInspection(rental.id)
  const { location } = useUserLocation()
  const { notify } = useUi()

  const [photos, setPhotos] = useState({})
  const [previews, setPreviews] = useState({})
  const [errors, setErrors] = useState({})
  const [marks, setMarks] = useState([])
  const [severity, setSeverity] = useState('scratch')
  const [cleanliness, setCleanliness] = useState(kind === 'start' ? 1 : null)
  const [confirmed, setConfirmed] = useState(false)
  const [demoBusy, setDemoBusy] = useState(false)
  const previewsRef = useRef({})

  useEffect(
    () => () => Object.values(previewsRef.current).forEach((url) => URL.revokeObjectURL(url)),
    [],
  )

  const angles = ['front', 'rear', 'left', 'right']
  if (kind === 'start' && cleanliness === 3) angles.push('interior')
  const missing = angles.filter((angle) => !photos[angle])

  const setPhoto = async (angle, original) => {
    const file = await downscaleImage(original)
    if (previewsRef.current[angle]) URL.revokeObjectURL(previewsRef.current[angle])
    const url = URL.createObjectURL(file)
    previewsRef.current[angle] = url
    setPhotos((current) => ({ ...current, [angle]: file }))
    setPreviews((current) => ({ ...current, [angle]: url }))
    setErrors((current) => ({ ...current, [angle]: undefined }))
  }

  const fillDemo = async () => {
    setDemoBusy(true)
    try {
      for (const angle of angles) {
        await setPhoto(angle, await makeDemoPhoto(car, angle))
      }
    } finally {
      setDemoBusy(false)
    }
  }

  const addMark = ({ x, y }) => {
    if (marks.length >= MAX_MARKS) return
    setMarks((current) => [...current, { x, y, severity, angle: y < 0.5 ? 'front' : 'rear' }])
    setConfirmed(false)
  }

  const removeMark = (mark, index) => {
    if (index === undefined) return // отметки из паспорта не удаляются
    setMarks((current) => current.filter((_, i) => i !== index))
  }

  const handleSubmit = () => {
    submit.mutate(
      {
        kind,
        photos: Object.fromEntries(angles.map((angle) => [angle, photos[angle]])),
        damages: marks,
        cleanliness,
        confirmed,
        location,
      },
      {
        onSuccess: (data) => {
          const count = data.new_damages.length
          // На старте новые отметки — защита клиента; на финише это повреждения за поездку.
          notify(`Акт #${data.inspection.seal_short} запечатан`, {
            description: !count
              ? 'Состояние машины зафиксировано в цепочке паспорта.'
              : kind === 'start'
                ? `Новых отметок: ${count}. Они не будут поставлены вам в вину.`
                : `Новых отметок: ${count}. Они зафиксированы в акте завершения поездки.`,
          })
          if (data.rental.compensation_minutes) {
            notify('Гарантия Signature', {
              description: `Первые ${data.rental.compensation_minutes} минут поездки — бесплатно.`,
            })
          } else if (kind === 'start' && cleanliness === 3 && signature) {
            notify('Гарантия Signature уже использована', {
              description: 'Бесплатные минуты доступны раз в 7 дней. Машину отправим на мойку.',
              tone: 'info',
            })
          }
          onDone?.(data)
          onClose()
        },
        onError: (error) => {
          const body = error.response?.data
          if (body?.angle) setErrors({ [body.angle]: body.detail })
        },
      },
    )
  }

  const title = kind === 'start' ? 'Осмотр перед поездкой' : 'Осмотр перед завершением'
  const signature = car.livery && car.livery !== 'none'
  // Поле приходит с бэкенда; если его нет — считаем гарантию доступной для машин Signature.
  const guarantee = rental.signature_guarantee || { available: signature, minutes: 15 }
  const knownCount = passport?.damages.length || 0

  return (
    <Modal
      title={title}
      subtitle="Четыре фото и отметки на силуэте — акт запечатывается в паспорт кузова"
      onClose={onClose}
      wide
    >
      <div className="inspect">
        <div className="inspect__stage">
          {['front', 'left', 'right', 'rear'].map((angle) => (
            <PhotoSlot
              key={angle}
              angle={angle}
              preview={previews[angle]}
              error={errors[angle]}
              onFile={(file) => setPhoto(angle, file)}
            />
          ))}
          <div className="inspect__car">
            <DamageSilhouette
              car={car}
              damages={passport?.damages || []}
              marks={marks}
              onAdd={addMark}
              onPick={removeMark}
            />
          </div>
        </div>

        <div className="inspect__side">
          <div>
            <div className="inspect__label">Отметить повреждение</div>
            <div className="segmented">
              {SEVERITIES.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={severity === value}
                  className={severity === value ? 'is-active' : ''}
                  onClick={() => setSeverity(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="fine-print">
              Нажмите на силуэт, чтобы поставить отметку.{' '}
              {knownCount
                ? `В паспорте уже ${plural(knownCount, ['отметка', 'отметки', 'отметок'])} — их отмечать не нужно.`
                : 'Известных повреждений у машины нет.'}
            </p>
          </div>

          {kind === 'start' && (
            <div>
              <div className="inspect__label">Чистота салона</div>
              <div className="segmented">
                {CLEANLINESS.map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={cleanliness === value}
                    className={cleanliness === value ? 'is-active' : ''}
                    onClick={() => setCleanliness(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {cleanliness === 3 && (
                <div className="inspect__interior">
                  <PhotoSlot
                    angle="interior"
                    preview={previews.interior}
                    error={errors.interior}
                    onFile={(file) => setPhoto('interior', file)}
                  />
                  <p className="fine-print">
                    {signature && guarantee.available
                      ? `Машина Signature: с фото салона первые ${guarantee.minutes} минут поездки бесплатно (не чаще раза в 7 дней).`
                      : signature
                        ? 'Гарантия Signature уже использована на этой неделе — машину отправим на мойку.'
                        : 'Мы отправим машину на мойку после вашей поездки.'}
                  </p>
                </div>
              )}
            </div>
          )}

          <label className={`confirm-row ${marks.length ? 'is-disabled' : ''}`}>
            <input
              type="checkbox"
              checked={confirmed}
              disabled={marks.length > 0}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            Всё как в паспорте — новых повреждений нет
          </label>

          <button type="button" className="btn btn--soft btn--block" onClick={fillDemo} disabled={demoBusy}>
            {demoBusy ? 'Готовим фото…' : 'Демо-фото для защиты'}
          </button>

          {submit.error && !submit.error.response?.data?.angle && (
            <p className="error-text">{extractError(submit.error)}</p>
          )}

          <button
            type="button"
            className="btn btn--cta btn--lg btn--block"
            disabled={missing.length > 0 || submit.isPending || (!confirmed && marks.length === 0)}
            onClick={handleSubmit}
          >
            {submit.isPending
              ? 'Запечатываем акт…'
              : missing.length
                ? `Ещё фото: ${missing.length}`
                : !confirmed && marks.length === 0
                  ? 'Подтвердите состояние'
                  : 'Запечатать акт'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
