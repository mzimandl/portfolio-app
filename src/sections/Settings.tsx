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
}

export interface NewInstrument {
    ticker: string|null;
    currency: string|null;
    type: string|null;
    evaluation: EvaluationType;
    eval_param: string|null;
}

interface SettingsState {
    instruments: Array<InstrumentDataRow>;
    currencies: Array<string>;
    types: Array<string>;
    new: {
        instrument: NewInstrument,
        currency: string|null,
        type: string|null,
    }
}

type CurrenciesResponse = Array<string>;
type TypesResponse = Array<string>;
export type InstrumentsResponse = Array<InstrumentDataRow>;

interface SettingsProps {}

export class Settings extends AbstractSection<SettingsProps, SettingsState> {

    sectionName = () => 'Settings';

    constructor(props: SettingsProps & SectionProps) {
        super(props);
        this.state = {
            instruments: [],
            currencies: [],
            types: [],
            new: {
                instrument: {
                    ticker: null,
                    currency: null,
                    type: null,
                    evaluation: 'yfinance',
                    eval_param: null,
                },
                currency: null,
                type: null,
            },
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

    addInstrument = () => {
        if (this.state.new.instrument.ticker && this.state.new.instrument.currency && this.state.new.instrument.type) {
            this.props.displayProgressBar(true);
            fetch('/instruments/new', {method: 'POST', body: JSON.stringify(this.state.new.instrument)})
                .then(res => {
                    this.loadInstruments().then(() => {
                        this.setState({
                            new: {
                                ...this.state.new,
                                instrument: {
                                    ticker: '',
                                    currency: '',
                                    type: '',
                                    evaluation: 'yfinance',
                                    eval_param: '',
                                }
                            }
                        });
                        this.props.displayProgressBar(false)
                    });
                });
        }
    }

    addCurrency = () => {
        if (this.state.new.currency) {
            this.props.displayProgressBar(true);
            fetch('/currencies/new', {method: 'POST', body: JSON.stringify({currency: this.state.new.currency})})
                .then(res => {
                    this.loadCurrencies().then(() => {
                        this.setState({
                            new: {
                                ...this.state.new,
                                currency: '',
                            }
                        });
                        this.props.displayProgressBar(false)
                    });
                });
        }
    }

    addType = () => {
        if (this.state.new.type) {
            this.props.displayProgressBar(true);
            fetch('/types/new', {method: 'POST', body: JSON.stringify({type: this.state.new.type})})
                .then(res => {
                    this.loadTypes().then(() => {
                        this.setState({
                            new: {
                                ...this.state.new,
                                type: '',
                            }
                        });
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
                                        <TableRow>
                                            <TableCell><TextField label="Currency" variant="outlined" size='small' margin='none' fullWidth value={this.state.new.currency}
                                                onChange={(e) => this.setState({new: {...this.state.new, currency: e.target.value}})} /></TableCell>
                                            <TableCell><IconButton onClick={this.addCurrency}><AddBox/></IconButton></TableCell>
                                        </TableRow>
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
                                        <TableRow>
                                            <TableCell><TextField label="Type" variant="outlined" size='small' margin='none' fullWidth value={this.state.new.type}
                                                onChange={(e) => this.setState({new: {...this.state.new, type: e.target.value}})} /></TableCell>
                                            <TableCell><IconButton onClick={this.addType}><AddBox/></IconButton></TableCell>
                                        </TableRow>
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
                                        <TableRow>
                                            <TableCell>
                                                <TextField label="Ticker" variant="outlined" size='small' margin='none' fullWidth value={this.state.new.instrument.ticker}
                                                onChange={(e) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, ticker: e.target.value}}})} />
                                            </TableCell>
                                            <TableCell>
                                                <Autocomplete
                                                    value={this.state.new.instrument.currency}
                                                    onChange={(e, newValue) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, currency: newValue}}})}
                                                    options={this.state.currencies}
                                                    renderInput={(params) => <TextField {...params} size='small' label="Currency" />}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Autocomplete
                                                    value={this.state.new.instrument.type}
                                                    onChange={(e, newValue) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, type: newValue}}})}
                                                    options={this.state.types}
                                                    renderInput={(params) => <TextField {...params} size='small' label="Type" />}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <FormControl fullWidth size='small'>
                                                    <InputLabel id="vmode-select-label">Evaluation</InputLabel>
                                                    <Select
                                                        labelId='vmode-select-label'
                                                        value={this.state.new.instrument.evaluation}
                                                        label="Value mode"
                                                        onChange={(e) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, evaluation: e.target.value as EvaluationType}}})}
                                                    >
                                                        <MenuItem value="yfinance">yfinance</MenuItem>
                                                        <MenuItem value="manual">manual</MenuItem>
                                                        <MenuItem value="http">http</MenuItem>
                                                    </Select>
                                                </FormControl>
                                            </TableCell>
                                            <TableCell>
                                                <TextField label="EvalParam" variant="outlined" size='small' margin='none' fullWidth value={this.state.new.instrument.eval_param}
                                                onChange={(e) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, eval_param: e.target.value}}})} />
                                            </TableCell>
                                            <TableCell><IconButton onClick={this.addInstrument}><AddBox/></IconButton></TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {this.state.instruments.map(
                                            (item, i) => <TableRow key={i}>
                                                <TableCell>{item.ticker}</TableCell>
                                                <TableCell>{item.currency}</TableCell>
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