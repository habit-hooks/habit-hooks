export default {
  scope: {
    exclude: ['tests/fixtures/**'],
  },
  smells: {
    'non-essential-comment': {
      exclude: ['tests/fixtures/**', 'habit-hooks.config.*'],
    },
  },
};
