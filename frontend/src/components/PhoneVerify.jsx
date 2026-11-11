import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { extractError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { useConfirmPhone, useSendPhoneCode } from '../hooks/useVerification'
import { useUi } from '../ui/UiProvider'
import { IconCheck, IconPhone } from './icons'

/** Подтверждение телефона кодом из SMS. В демо-режиме «SMS» показывается прямо на экране. */
export default function PhoneVerify({ onDone }) {
  const { user } = useAuth()
  const send = useSendPhoneCode()
  const confirm = useConfirmPhone()
  const { notify } = useUi()
  const [code, setCode] = useState('')
  const [resendAt, setResendAt] = useState(0)
  const [now, setNow] = useState(Date.now())
  const sent = send.data

  useEffect(() => {
    if (!resendAt) return undefined
    const timer = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(timer)
  }, [resendAt])

  if (user?.phone_verified) {
    return (
      <div className="phone-ok">
        <span className="phone-ok__icon"><IconCheck width={18} height={18} strokeWidth={3} /></span>
        <div>
          <b>{user.phone_number}</b>
          <small>Номер подтверждён</small>
        </div>
      </div>
    )
  }

  const requestCode = () =>
    send.mutate(undefined, {
      onSuccess: (data) => {
        setResendAt(Date.now() + data.resend_in * 1000)
        setCode('')
      },
      onError: (error) => {
        const wait = error?.response?.data?.resend_in
        if (wait) setResendAt(Date.now() + Number(wait) * 1000)
      },
    })

  const submit = (event) => {
    event.preventDefault()
    confirm.mutate(code, {
      onSuccess: () => {
        notify('Телефон подтверждён', { description: 'Можно продолжать проверку.' })
        onDone?.()
      },
    })
  }

  const wait = Math.max(0, Math.ceil((resendAt - now) / 1000))

  return (
    <div className="phone-verify">
      <div className="phone-verify__number">
        <IconPhone width={20} height={20} />
        <div>
          <b>{user?.phone_number || 'Номер не указан'}</b>
          <small>
            Код придёт в SMS. Другой номер?{' '}
            <Link to="/profile#settings" className="link-gold">
              Изменить в профиле
            </Link>
          </small>
        </div>
      </div>

      {sent?.demo_code && (
        <div className="sms-bubble" role="status">
          <small>SMS · Рули · демо-режим</small>
          Рули: код <b className="num">{sent.demo_code}</b>. Никому его не сообщайте.
        </div>
      )}

      {sent ? (
        <form className="phone-verify__form" onSubmit={submit}>
          <input
            className="code-input num"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="••••••"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
            aria-label="Код из SMS"
            autoFocus
          />
          <button type="submit" className="btn btn--cta btn--lg" disabled={code.length !== 6 || confirm.isPending}>
            {confirm.isPending ? 'Проверяем…' : 'Подтвердить'}
          </button>
          <button type="button" className="link-gold" disabled={wait > 0 || send.isPending} onClick={requestCode}>
            {wait > 0 ? `Новый код через ${wait} с` : 'Отправить код ещё раз'}
          </button>
        </form>
      ) : (
        <button type="button" className="btn btn--cta btn--lg" disabled={send.isPending || !user?.phone_number} onClick={requestCode}>
          {send.isPending ? 'Отправляем…' : 'Получить код'}
        </button>
      )}

      {(send.error || confirm.error) && <p className="error-text">{extractError(confirm.error || send.error)}</p>}
    </div>
  )
}
