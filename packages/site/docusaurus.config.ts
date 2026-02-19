import type { Config } from '@docusaurus/types';
import { themes as prismThemes } from 'prism-react-renderer';

const repo = process.env.GITHUB_REPOSITORY;
const owner = process.env.GITHUB_REPOSITORY_OWNER || 'adpena';
const project = (repo?.split('/')[1] || 'cinderx-community').trim();
const isCi = process.env.GITHUB_ACTIONS === 'true';
const isUserPages = project === `${owner}.github.io`;

const config: Config = {
  title: 'CinderX Community',
  tagline: 'Performance extensions for CPython 3.14+',
  favicon: 'img/favicon.svg',

  url: isCi ? `https://${owner}.github.io` : 'http://localhost:3000',
  baseUrl: isCi ? (isUserPages ? '/' : `/${project}/`) : '/',

  organizationName: owner,
  projectName: project,

  onBrokenLinks: 'throw',
  trailingSlash: false,
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn'
    }
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en']
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: `https://github.com/${owner}/${project}/edit/main/packages/site/`
        },
        blog: {
          showReadingTime: true,
          editUrl: `https://github.com/${owner}/${project}/edit/main/packages/site/`
        },
        theme: {
          customCss: './src/css/custom.css'
        }
      }
    ]
  ],

  plugins: [
    [
      '@easyops-cn/docusaurus-search-local',
      {
        hashed: true,
        indexDocs: true,
        indexBlog: true,
        docsRouteBasePath: '/docs',
        blogRouteBasePath: '/blog',
        language: ['en'],
        highlightSearchTermsOnTargetPage: true,
        explicitSearchResultPath: true
      }
    ]
  ],

  themeConfig: {
    image: 'img/social-card.svg',
    navbar: {
      title: 'CinderX Community',
      logo: {
        alt: 'CinderX Community',
        src: 'img/logo.svg'
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs'
        },
        {
          to: '/docs/benchmarks/results-placeholder',
          label: 'Results',
          position: 'left'
        },
        {
          to: '/docs/compatibility/platform-support',
          label: 'Compatibility',
          position: 'left'
        },
        { to: '/docs/tutorials/django-dummy-service', label: 'Tutorials', position: 'left' },
        { to: '/docs/faq', label: 'FAQ', position: 'left' },
        { to: '/blog', label: 'Blog', position: 'left' },
        {
          href: `https://github.com/${owner}/${project}`,
          label: 'GitHub',
          position: 'right'
        }
      ]
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            { label: 'Overview', to: '/docs/overview' },
            { label: 'Install', to: '/docs/install' },
            { label: 'Compatibility', to: '/docs/compatibility/matrix' },
            { label: 'Benchmarks', to: '/docs/benchmarks' },
            { label: 'FAQ', to: '/docs/faq' }
          ]
        },
        {
          title: 'Project',
          items: [{ label: 'GitHub', href: `https://github.com/${owner}/${project}` }]
        },
        {
          title: 'Sources',
          items: [
            { label: 'CinderX README', href: 'https://github.com/facebookincubator/cinderx' },
            {
              label: 'Meta Engineering post',
              href: 'https://engineering.fb.com/2023/10/05/developer-tools/python-312-meta-new-features/'
            },
            { label: 'pyperformance', href: 'https://pyperformance.readthedocs.io/' }
          ]
        }
      ],
      copyright: `Copyright © ${new Date().getFullYear()} CinderX Community Contributors`
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula
    }
  }
};

export default config;
