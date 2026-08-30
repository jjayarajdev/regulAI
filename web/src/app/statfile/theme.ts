// RegAssure antd theme — deliberately antd-NATIVE: default blue, default
// radius, default type stack, classic dark-navy sider. The redesigned screens
// speak Ant Design's own language; only the brand strings are ours. Legacy
// (not-yet-migrated) screens keep their scoped .sf styles.
export const REGASSURE_THEME = {
  components: {
    Layout: { siderBg: '#001529', headerBg: '#ffffff' },
  },
} as const;

// Brand strings — the product is RegAssure; internal module names keep the
// statfile heritage.
export const BRAND = 'RegAssure';
export const BRAND_TAG = 'Regulatory assurance fabric';
