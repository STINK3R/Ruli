import { useState } from 'react'
import { usePassport, useVerifyChain } from '../hooks/usePassport'
import DamageSilhouette from './DamageSilhouette'
import Modal from './Modal'
import { IconCheck, IconSeal } from './icons'

const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) : '—'

function daysAgo(value) {
  if (!value) return null
  return Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 86_400_000))
}

export function IntegrityLine({ result }) {
  if (!result) return null
  return result.ok ? (
    <div className="integrity integrity--ok">
      <IconCheck width={15} height={15} strokeWidth={2.6} />
      Цепочка цела — актов проверено: {result.checked}
    </div>
  ) : (
    <div className="integrity integrity--broken">
      Цепочка нарушена на акте #{result.broken_seal}: {result.reason_text}
    </div>
  )
}

export default function PassportModal({ car, onClose }) {
  const { data: passport, isLoading } = usePassport(car.id)
  const verify = useVerifyChain(car.id)
  const [active, setActive] = useState(null)

  const cleanedDays = daysAgo(passport?.last_cleaned_at)

  return (
    <Modal
      title="Паспорт кузова"
      subtitle={`${car.title} · ${car.license_plate}`}
      onClose={onClose}
      wide
    >
      {isLoading || !passport ? (
        <div className="skeleton" style={{ height: 320 }} />
      ) : (
        <div className="passport">
          <div className="passport__visual">
            <DamageSilhouette
              car={car}
              damages={passport.damages}
              onPick={setActive}
              activeId={active?.id}
            />
            <div className="passport__legend">
              <span><i className="pin pin--known" /> Известно</span>
              <span><i className="pin pin--new" /> Новое</span>
            </div>
          </div>

          <div className="passport__info">
            {active ? (
              <div className="damage-card fade-up">
                {active.photo_url && <img src={active.photo_url} alt="" />}
                <div className="damage-card__title">{active.severity_display}</div>
                <div className="muted">
                  {active.status_display} · впервые {formatDate(active.first_seen_at)} · акт #
                  {active.seal_short}
                </div>
                <p className="muted">
                  За отметки, которые уже есть в паспорте, клиент не отвечает.
                </p>
              </div>
            ) : (
              <p className="muted">
                {passport.damages.length
                  ? 'Нажмите на отметку, чтобы увидеть фото и акт, где её зафиксировали.'
                  : 'Известных повреждений нет.'}
              </p>
            )}

            <dl className="passport__facts">
              <div>
                <dt>Актов в цепочке</dt>
                <dd>{passport.chain_length}</dd>
              </div>
              <div>
                <dt>Последний акт</dt>
                <dd>{passport.last_seal ? `#${passport.last_seal}` : '—'}</dd>
              </div>
              <div>
                <dt>Чистота салона</dt>
                <dd>{passport.cleanliness_score ? `${String(passport.cleanliness_score).replace('.', ',')} из 5` : '—'}</dd>
              </div>
              <div>
                <dt>Мойка</dt>
                <dd>{cleanedDays === null ? '—' : cleanedDays === 0 ? 'сегодня' : `${cleanedDays} дн. назад`}</dd>
              </div>
            </dl>

            {passport.is_signature && (
              <div className="signature-note">
                <IconSeal width={18} height={18} />
                <div>
                  <b>Стандарт Signature.</b> Если машина грязная — отметьте это при осмотре и
                  приложите фото салона: первые 15 минут поездки будут бесплатными (не чаще раза в 7 дней).
                </div>
              </div>
            )}

            <IntegrityLine result={verify.data || passport.integrity} />
            <button
              type="button"
              className="btn btn--dark btn--block"
              onClick={() => verify.mutate()}
              disabled={verify.isPending}
            >
              {verify.isPending ? 'Пересчитываем хэши…' : 'Проверить целостность сейчас'}
            </button>
            <p className="fine-print">
              Каждый акт запечатан хэшем SHA-256, в который входит хэш предыдущего акта этой машины.
              Подмену фото или данных задним числом видно по разрыву цепочки.
            </p>
          </div>
        </div>
      )}
    </Modal>
  )
}
