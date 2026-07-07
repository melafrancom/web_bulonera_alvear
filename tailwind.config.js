/** @type {import('tailwindcss').Config} */
const typography = require('@tailwindcss/typography');

module.exports = {
  content: [
    './templates/**/*.html',
    './*/templates/**/*.html',
    './static/js/**/*.js',
  ],
  darkMode: 'class',
  safelist: [
    'bg-navbar-bg',
    'text-navbar-text',
    'bg-primary-600',
    'bg-primary-700',
    'bg-primary-800',
    'from-primary-600',
    'to-primary-700',
    'to-primary-800',
    'dark:from-primary-800',
    'dark:to-primary-900',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: 'var(--color-primary-800, #1E40AF)',
          50: 'var(--color-primary-50, #EFF6FF)',
          100: 'var(--color-primary-100, #DBEAFE)',
          200: 'var(--color-primary-200, #BFDBFE)',
          300: 'var(--color-primary-300, #93C5FD)',
          400: 'var(--color-primary-400, #60A5FA)',
          500: 'var(--color-primary-500, #3B82F6)',
          600: 'var(--color-primary-600, #2563EB)',
          700: 'var(--color-primary-700, #1D4ED8)',
          800: 'var(--color-primary-800, #1E40AF)',
          900: 'var(--color-primary-900, #1E3A8A)',
        },
        'navbar-bg': 'var(--color-navbar-bg, #1B3A5C)',
        'navbar-text': 'var(--color-navbar-text, #ffffff)',
        // Color de fondo suave para light mode
        'soft-bg': 'var(--color-soft-bg, #F0F9FF)',
        accent: {
          DEFAULT: '#F59E0B',
          50: '#FFFBEB',
          100: '#FEF3C7',
          200: '#FDE68A',
          300: '#FCD34D',
          400: '#FBBF24',
          500: '#F59E0B',
          600: '#D97706',
          700: '#B45309',
          800: '#92400E',
          900: '#78350F',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      typography: (theme) => ({
        DEFAULT: {
          css: {
            maxWidth: 'none',
            color: theme('colors.gray.800'),
            h2: {
              color: theme('colors.gray.900'),
              fontWeight: '700',
              fontSize: '1.75rem',
              marginTop: '2.5rem',
              marginBottom: '1rem',
              borderBottom: `2px solid ${theme('colors.primary.200')}`,
              paddingBottom: '0.5rem',
            },
            h3: {
              color: theme('colors.gray.800'),
              fontWeight: '600',
              fontSize: '1.35rem',
              marginTop: '2rem',
            },
            a: {
              color: theme('colors.primary.600'),
              textDecoration: 'underline',
              fontWeight: '500',
              '&:hover': { color: theme('colors.primary.800') },
            },
            blockquote: {
              borderLeftColor: theme('colors.accent.400'),
              backgroundColor: theme('colors.accent.50'),
              padding: '1rem 1.5rem',
              borderRadius: '0.5rem',
              fontStyle: 'normal',
            },
            'ul > li::marker': { color: theme('colors.primary.500') },
            'ol > li::marker': { color: theme('colors.primary.500') },
            strong: { color: theme('colors.gray.900') },
            img: { borderRadius: '0.75rem', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' },
          },
        },
        invert: {
          css: {
            color: theme('colors.gray.300'),
            h2: {
              color: theme('colors.white'),
              borderBottomColor: theme('colors.slate.700'),
            },
            h3: { color: theme('colors.gray.200') },
            a: {
              color: theme('colors.blue.400'),
              '&:hover': { color: theme('colors.blue.300') },
            },
            blockquote: {
              borderLeftColor: theme('colors.accent.500'),
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
            },
            strong: { color: theme('colors.white') },
          },
        },
      }),
    },
  },
  plugins: [typography],
}
