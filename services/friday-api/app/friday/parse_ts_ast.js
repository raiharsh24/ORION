import ts from 'typescript';
import fs from 'fs';

if (process.argv.length < 3) {
  console.log(JSON.stringify({ imports: [], exports: [], interfaces: [], classes: [], enums: [], functions: [], hooks: [], reactComponents: [] }));
  process.exit(0);
}

const filePath = process.argv[2];
try {
  const code = fs.readFileSync(filePath, 'utf-8');
  const sourceFile = ts.createSourceFile(filePath, code, ts.ScriptTarget.Latest, true);

  const imports = [];
  const exportsList = [];
  const interfaces = [];
  const classes = [];
  const enums = [];
  const functions = [];
  const hooks = [];
  const reactComponents = [];

  function visit(node) {
    // 1. Imports
    if (ts.isImportDeclaration(node)) {
      if (node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
        imports.push(node.moduleSpecifier.text);
      }
    }

    // 2. Export Declarations (e.g. export const x = ...)
    if (node.modifiers && node.modifiers.some(m => m.kind === ts.SyntaxKind.ExportKeyword)) {
      if (ts.isVariableStatement(node)) {
        node.declarationList.declarations.forEach(dec => {
          if (dec.name && ts.isIdentifier(dec.name)) {
            exportsList.push(dec.name.text);
          }
        });
      } else if ((ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isFunctionDeclaration(node) || ts.isEnumDeclaration(node)) && node.name) {
        exportsList.push(node.name.text);
      }
    }

    // 3. Classes
    if (ts.isClassDeclaration(node) && node.name) {
      const className = node.name.text;
      const heritage = [];
      const implementsList = [];
      
      if (node.heritageClauses) {
        node.heritageClauses.forEach(clause => {
          if (clause.token === ts.SyntaxKind.ExtendsKeyword) {
            clause.types.forEach(t => heritage.push(t.expression.getText(sourceFile)));
          } else if (clause.token === ts.SyntaxKind.ImplementsKeyword) {
            clause.types.forEach(t => implementsList.push(t.expression.getText(sourceFile)));
          }
        });
      }

      classes.push({
        name: className,
        extends: heritage,
        implements: implementsList
      });
    }

    // 4. Interfaces
    if (ts.isInterfaceDeclaration(node) && node.name) {
      interfaces.push(node.name.text);
    }

    // 5. Enums
    if (ts.isEnumDeclaration(node) && node.name) {
      enums.push(node.name.text);
    }

    // 6. Functions (Functions, Hooks, and React Components)
    if (ts.isFunctionDeclaration(node) && node.name) {
      const funcName = node.name.text;
      classifyFunction(funcName);
    } else if (ts.isVariableStatement(node)) {
      node.declarationList.declarations.forEach(dec => {
        if (dec.name && ts.isIdentifier(dec.name) && dec.initializer && 
            (ts.isArrowFunction(dec.initializer) || ts.isFunctionExpression(dec.initializer))) {
          classifyFunction(dec.name.text);
        }
      });
    }

    ts.forEachChild(node, visit);
  }

  function classifyFunction(name) {
    if (name.startsWith('use') && name[3] && name[3] === name[3].toUpperCase()) {
      hooks.push(name);
    } else if (name[0] && name[0] === name[0].toUpperCase()) {
      reactComponents.push(name);
    } else {
      functions.push(name);
    }
  }

  visit(sourceFile);

  console.log(JSON.stringify({
    imports,
    exports: exportsList,
    interfaces,
    classes,
    enums,
    functions,
    hooks,
    reactComponents
  }, null, 2));

} catch (err) {
  console.log(JSON.stringify({ error: err.message, imports: [], exports: [], interfaces: [], classes: [], enums: [], functions: [], hooks: [], reactComponents: [] }));
}
