import { Button, Card, Popconfirm, Space, Table, Typography, Upload } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { useDeleteDocument, useDocuments, useKnowledgeBases, useUploadDocument } from '../api/hooks'
import { FormPageHeader } from '../components/FormPageHeader'
import { UPLOAD_ACCEPT } from '../constants'
import { useMessage } from '../hooks/useMessage'

export function KnowledgeBaseDetailPage() {
  const { t } = useTranslation()
  const message = useMessage()
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const kbs = useKnowledgeBases()
  const kb = (kbs.data ?? []).find((item) => item.id === id) ?? null
  const documents = useDocuments(id ?? null)
  const upload = useUploadDocument(id ?? '')
  const remove = useDeleteDocument(id ?? '')

  if (kbs.isLoading) {
    return (
      <>
        <FormPageHeader title={t('kb.title')} backTo="/kb" />
        <Typography.Text type="secondary">{t('common.loading')}</Typography.Text>
      </>
    )
  }

  if (!kb) {
    return (
      <>
        <FormPageHeader title={t('kb.title')} backTo="/kb" />
        <Typography.Text type="secondary">{t('kb.notFound')}</Typography.Text>
        <Button type="link" onClick={() => navigate('/kb')}>
          {t('common.back')}
        </Button>
      </>
    )
  }

  return (
    <>
      <FormPageHeader title={kb.name} backTo="/kb" />
      <Card>
        <Typography.Paragraph type="secondary">
          {kb.description || t('common.noDescription')}
        </Typography.Paragraph>
        <Space wrap>
          <Typography.Text>
            {t('kb.ingestPipelineLabel', { id: kb.ingest_pipeline_id ?? t('common.unbound') })}
          </Typography.Text>
        </Space>
        <div style={{ margin: '16px 0' }}>
          <Typography.Paragraph type="secondary">{t('kb.uploadHint')}</Typography.Paragraph>
          <Upload
            accept={UPLOAD_ACCEPT}
            maxCount={1}
            showUploadList={false}
            beforeUpload={(file) => {
              upload.mutate(file, {
                onSuccess: (doc) => {
                  if (doc.status === 'indexed') {
                    message.success(t('kb.uploadedIndexed', { name: file.name }))
                  } else if (doc.status === 'failed') {
                    message.error(t('kb.ingestFailed'))
                  } else {
                    message.success(t('kb.uploaded', { name: file.name }))
                  }
                },
                onError: (error) =>
                  message.error(error instanceof Error ? error.message : t('kb.uploadFailed')),
              })
              return false
            }}
          >
            <Button loading={upload.isPending}>{t('common.upload')}</Button>
          </Upload>
        </div>
        <Table
          rowKey="id"
          size="small"
          loading={documents.isLoading || upload.isPending || remove.isPending}
          dataSource={documents.data}
          pagination={false}
          columns={[
            { title: t('common.title'), dataIndex: 'title' },
            { title: t('common.status'), dataIndex: 'status', width: 120 },
            {
              title: '',
              width: 80,
              render: (_, row) => (
                <Popconfirm
                  title={t('kb.deleteDocumentConfirm')}
                  onConfirm={async () => {
                    try {
                      await remove.mutateAsync(row.id)
                      message.success(t('common.deleted'))
                    } catch (error) {
                      message.error(
                        error instanceof Error ? error.message : t('common.deleteFailed'),
                      )
                    }
                  }}
                >
                  <Button danger type="link" size="small">
                    {t('common.delete')}
                  </Button>
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>
    </>
  )
}
