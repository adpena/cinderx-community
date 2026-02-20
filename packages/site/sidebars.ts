import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'overview',
    'install',
    'compatibility',
    'benchmarks',
    'contributing',
    'faq',
    'glossary',
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/what-is-cinderx',
        'getting-started/installation',
        'getting-started/quick-verification'
      ]
    },
    {
      type: 'category',
      label: 'Concepts',
      items: ['concepts/cinderx-vs-cinder', 'concepts/jit-compiler', 'concepts/static-python']
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/overview',
        'architecture/jit-pipeline',
        'architecture/static-python-runtime',
        'architecture/runtime-hooks-cpython',
        'architecture/debugging-observability'
      ]
    },
    {
      type: 'category',
      label: 'Generated',
      items: [
        'generated/introspection-overview',
        'generated/symbol-inventory',
        'generated/build-options',
        'generated/test-taxonomy'
      ]
    },
    {
      type: 'category',
      label: 'Compatibility',
      items: [
        'compatibility/cinderx-runtime-setup',
        'compatibility/matrix',
        'compatibility/platform-support',
        'compatibility/c-extensions-and-abi',
        'compatibility/packaging-and-deployment',
        'compatibility/test-strategy',
        'compatibility/production-checklist',
        'compatibility/known-packages'
      ]
    },
    {
      type: 'category',
      label: 'Tutorials',
      items: [
        'tutorials/cpython-project-quickstart',
        'tutorials/cinderx-runtime-scripts',
        'tutorials/simple-benchmark-usage',
        'tutorials/django-dummy-service',
        'tutorials/measure-speedups'
      ]
    },
    {
      type: 'category',
      label: 'Benchmarks',
      items: [
        'benchmarks/taxonomy',
        'benchmarks/methodology',
        'benchmarks/planned-suites',
        'benchmarks/results-placeholder'
      ]
    },
    {
      type: 'category',
      label: 'Contributing',
      items: [
        'contributing/local-dev-setup',
        'contributing/code-style-and-tests',
        'contributing/docs-writing-rules',
        'contributing/good-first-issues',
        'contributing/how-to-add-benchmark'
      ]
    }
  ]
};

export default sidebars;
