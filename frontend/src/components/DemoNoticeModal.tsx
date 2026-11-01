import type { ReactNode } from 'react'
import { Button, Modal } from './ui'

export interface DemoNoticeModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  buttonText?: string
  buttonTestId?: string
}

/**
 * Shared modal for portal demo environment notices.
 * Displays on initial page load / refresh and dismisses via button, backdrop, or Escape.
 * Portal-specific messaging is passed as children.
 */
export function DemoNoticeModal({
  open,
  onClose,
  title,
  children,
  buttonText = 'Continue',
  buttonTestId,
}: DemoNoticeModalProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <Button onClick={onClose} data-testid={buttonTestId}>
          {buttonText}
        </Button>
      }
    >
      {children}
    </Modal>
  )
}
