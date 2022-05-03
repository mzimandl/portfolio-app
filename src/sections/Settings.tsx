import React from 'react';
import { AbstractSection, SectionProps } from '../common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Grid, InputLabel, Select, MenuItem, Autocomplete, CardContent, Card } from '@mui/material';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';


type EvaluationType = 'yfinance'|'manual'|'http';

export interface InstrumentDataRow {
    ticker: string;
    currency: string;
    type: string;
    evaluation: EvaluationType;
    eval_param: string;
    dividend_currency: string;
}

export interface NewInstrument {
    ticker: string|null;
    currency: string|null;
    type: string|null;
    evaluation: EvaluationType;
    eval_param: string|null;
    dividend_currency: string|null;
}

interface SettingsState {
    instruments: Array<InstrumentDataRow>;
    currencies: Array<string>;
    types: Array<string>;
}

type CurrenciesResponse = Array<string>;
type TypesResponse = Array<string>;
export type InstrumentsResponse = Array<InstrumentDataRow>;

interface SettingsProps {}
interface NewStringProps {
    stringName: string;
    addHandler: (value:string|null) => void;
}
interface NewInstrumentProps {
    types: Array<string>;
    currencies: Array<string>;
    addInstrument: (newInstrument:NewInstrument) => void;
}

class NewStringTableRow extends React.Component<NewStringProps, {value: string|null}> {

    constructor(props: NewStringProps) {
        super(props);
        this.state = {value: null};
    }

    render() {
        return <TableRow>
            <TableCell>
                <TextField label={this.props.stringName} variant="outlined" size='small' margin='none'
                           fullWidth value={this.state.value} onChange={(e) => this.setState({value: e.target.value})} />
            </TableCell>
            <TableCell>
                <IconButton onClick={e => this.props.addHandler(this.state.value)}><AddBox/></IconButton>
            </TableCell>
        </TableRow>
    }
}

class NewInstrumentTableRow extends React.Component<NewInstrumentProps, NewInstrument> {

    constructor(props: NewInstrumentProps) {
        super(props);
        this.state = {
            ticker: null,
            currency: null,
            type: null,
            evaluation: 'yfinance',
            eval_param: null,
            dividend_currency: null,
        };
    }

    render() {
        return <TableRow>
            <TableCell>
                <TextField label="Ticker" variant="outlined" size='small' margin='none' fullWidth value={this.state.ticker}
                onChange={(e) => this.setState({ticker: e.target.value})} />
            </TableCell>
            <TableCell>
                <Autocomplete
                    value={this.state.currency}
                    onChange={(e, newValue) => this.setState({currency: newValue})}
                    options={this.props.currencies}
                    renderInput={(params) => <TextField {...params} size='small' label="Currency" />}
                />
            </TableCell>
            <TableCell>
                <Autocomplete
                    value={this.state.dividend_currency}
                    onChange={(e, newValue) => this.setState({dividend_currency: newValue})}
                    options={this.props.currencies}
                    renderInput={(params) => <TextField {...params} size='small' label="Dividend Currency" />}
                />
            </TableCell>
            <TableCell>
                <Autocomplete
                    value={this.state.type}
                    onChange={(e, newValue) => this.setState({type: newValue})}
                    options={this.props.types}
                    renderInput={(params) => <TextField {...params} size='small' label="Type" />}
                />
            </TableCell>
            <TableCell>
                <FormControl fullWidth size='small'>
                    <InputLabel id="vmode-select-label">Evaluation</InputLabel>
                    <Select
                        labelId='vmode-select-label'
                        value={this.state.evaluation}
                        label="Value mode"
                        onChange={(e) => this.setState({evaluation: e.target.value as EvaluationType})}
                    >
                        <MenuItem value="yfinance">yfinance</MenuItem>
                        <MenuItem value="manual">manual</MenuItem>
                        <MenuItem value="http">http</MenuItem>
                    </Select>
                </FormControl>
            </TableCell>
            <TableCell>
                <TextField label="EvalParam" variant="outlined" size='small' margin='none' fullWidth value={this.state.eval_param}
                onChange={(e) => this.setState({eval_param: e.target.value})} />
            </TableCell>
            <TableCell><IconButton onClick={e => this.props.addInstrument(this.state)}><AddBox/></IconButton></TableCell>
        </TableRow>
    }
}

export class Settings extends AbstractSection<SettingsProps, SettingsState> {

    sectionName = () => 'Settings';

    constructor(props: SettingsProps & SectionProps) {
        super(props);
        this.state = {
            instruments: [],
            currencies: [],
            types: [],
        };

        this.addInstrument = this.addInstrument.bind(this);
        this.addCurrency = this.addCurrency.bind(this);
        this.addType = this.addType.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadCurrencies().then(() =>
            this.loadTypes().then(() =>
                this.loadInstruments().then(() =>
                this.props.displayProgressBar(false)
                )
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then<InstrumentsResponse>(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadCurrencies = () => {
        return fetch('/currencies/list')
            .then<CurrenciesResponse>(res => res.json())
            .then(currencies => this.setState({currencies}));
    }

    loadTypes = () => {
        return fetch('/types/list')
            .then<TypesResponse>(res => res.json())
            .then(types => this.setState({types}));
    }

    addInstrument = (newInstrument: NewInstrument) => {
        if (newInstrument.ticker && newInstrument.currency && newInstrument.type) {
            this.props.displayProgressBar(true);
            fetch('/instruments/new', {method: 'POST', body: JSON.stringify(newInstrument)})
                .then(res => {
                    this.loadInstruments().then(() => {
                        this.props.displayProgressBar(false)
                    });
                });
        }
    }

    addCurrency = (currency:string|null) => {
        if (currency) {
            this.props.displayProgressBar(true);
            fetch('/currencies/new', {method: 'POST', body: JSON.stringify({currency})})
                .then(res => {
                    this.loadCurrencies().then(() => {
                        this.props.displayProgressBar(false)
                    });
                });
        }
    }

    addType = (type:string|null) => {
        if (type) {
            this.props.displayProgressBar(true);
            fetch('/types/new', {method: 'POST', body: JSON.stringify({type})})
                .then(res => {
                    this.loadTypes().then(() => {
                        this.props.displayProgressBar(false)
                    });
                });
        }
    }

    render() {
        return <Box>
            <Grid container spacing={2}>
                <Grid item xs={2}>
                    <Card elevation={3}>
                        <CardContent>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <NewStringTableRow stringName="Currency" addHandler={this.addCurrency} />
                                    </TableHead>
                                    <TableBody>
                                        {this.state.currencies.map(
                                            (item, i) => <TableRow key={i}>
                                                <TableCell colSpan={2}>{item} {item === this.props.config.base_currency ? '(base)' : null}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={2}>
                    <Card elevation={3}>
                        <CardContent>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <NewStringTableRow stringName="Type" addHandler={this.addType} />
                                    </TableHead>
                                    <TableBody>
                                        {this.state.types.map(
                                            (item, i) => <TableRow key={i}>
                                                <TableCell colSpan={2}>{item}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={8}>
                    <Card elevation={3}>
                        <CardContent>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <NewInstrumentTableRow types={this.state.types} currencies={this.state.currencies} addInstrument={this.addInstrument} />
                                    </TableHead>
                                    <TableBody>
                                        {this.state.instruments.map(
                                            (item, i) => <TableRow key={i}>
                                                <TableCell>{item.ticker}</TableCell>
                                                <TableCell>{item.currency}</TableCell>
                                                <TableCell>{item.dividend_currency}</TableCell>
                                                <TableCell>{item.type}</TableCell>
                                                <TableCell>{item.evaluation}</TableCell>
                                                <TableCell colSpan={2}>{item.eval_param}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </Box>
    }
}