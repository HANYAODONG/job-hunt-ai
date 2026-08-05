import React from 'react';
import { Button, Space, Typography } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';

const PageHeading = ({ eyebrow = '岗位能力智能平台', title, description, action, children }) => (
  <div className="page-heading">
    <div>
      <div className="page-eyebrow"><span />{eyebrow}</div>
      <Typography.Title level={2}>{title}</Typography.Title>
      {description && <Typography.Paragraph>{description}</Typography.Paragraph>}
    </div>
    <Space className="page-heading-actions">
      {children}
      {action && <Button type="primary" icon={<ArrowRightOutlined />} onClick={action.onClick}>{action.label}</Button>}
    </Space>
  </div>
);

export default PageHeading;
