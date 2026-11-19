"""Syntactic generation aid from live admitted schemas. Not an authorization gate.

Strict bounded shape profile. Only supported keywords/types are accepted;
semantic bounds, equal lengths, dimensionality, and provenance checked by
original MEL codecs after parse. No task answers or requested values embedded.
"""
import json
import re


def literal(text):return json.dumps(text,ensure_ascii=True)


def request_grammar(schemas):
    if not isinstance(schemas,list) or not 1<=len(schemas)<=5:raise ValueError('bounded schema selection')
    rules=[];names=[];next_id=0
    def create(schema,depth=0):
        nonlocal next_id
        if depth>8:raise ValueError('schema depth')
        label=f'arg{next_id}';next_id+=1
        kind=schema['type']
        if kind=='object':
            props=schema['properties'];req=schema['required']
            if schema.get('additionalProperties') is not False or set(req)!=set(props) or len(req)!=len(props):raise ValueError('closed schema required')
            fields=[literal(json.dumps(key))+ ' ws ":" ws '+create(props[key],depth+1) for key in sorted(props)]
            body='"{" ws '+' ws "," ws '.join(fields)+' ws "}"'
        elif kind=='array':
            low,high=schema['minItems'],schema['maxItems']
            if type(low) is not int or type(high) is not int or not 0<=low<=high<=32 or high==0:raise ValueError('array limit')
            child=create(schema['items'],depth+1)
            seq=child+f' (ws "," ws {child})'+'{'+str(max(0,low-1))+','+str(high-1)+'}'
            body='"[" ws '+ ('('+seq+')?' if low==0 else seq)+' ws "]"'
        elif kind=='number':body='number'
        elif kind=='string':
            pattern=schema.get('pattern')
            if pattern=='^[01]+$':body='"\\\"" [01]{1,1024} "\\\""'
            elif pattern=='^(?:[A-Za-z][A-Za-z0-9_]{0,23}|1)$':body='"\\\"" ([A-Za-z] [A-Za-z0-9_]{0,23} | "1") "\\\""'
            else:raise ValueError('unknown string profile')
        else:raise ValueError('unsupported schema type')
        rules.append(label+' ::= '+body);return label
    for i,s in enumerate(schemas):
        if s.get('type')!='function':raise ValueError('function offer')
        f=s['function'];name=f['name']
        if not re.fullmatch(r'mel_[a-z_]+',name) or name in names:raise ValueError('tool name')
        names.append(name);arg=create(f['parameters']);rules.append(f'tool{i} ::= "{{" ws {literal(json.dumps("tool"))} ws ":" ws {literal(json.dumps(name))} ws "," ws {literal(json.dumps("arguments"))} ws ":" ws {arg} ws "}}"')
    rules.append('refuse ::= '+literal('{"tool":"refuse","arguments":{}}'))
    return '\n'.join(['root ::= ws ('+' | '.join(f'tool{i}' for i in range(len(names)))+' | refuse) ws',*rules,'ws ::= [ \\t\\n\\r]*','number ::= "-"? ("0" | [1-9] [0-9]{0,8}) ("." [0-9]{1,16})? ([eE] [+-]? [0-9]{1,3})?'])+'\n'
