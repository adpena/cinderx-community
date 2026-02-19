/// <reference types="@docusaurus/module-type-aliases" />

declare module '*.module.css' {
  const classes: { readonly [key: string]: string };
  export default classes;
}
